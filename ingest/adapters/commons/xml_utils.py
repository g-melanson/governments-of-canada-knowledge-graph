"""Streaming XML helpers for House of Commons feeds (namespace-safe, xsi:nil)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def path_suffix(path: tuple[str, ...], n: int) -> tuple[str, ...]:
    return path[-n:] if len(path) >= n else path


def parse_section_label(label: str | None) -> str | None:
    if label is None:
        return None
    text = label.strip()
    return text or None


def child_text(parent: ET.Element, tag: str) -> str | None:
    for child in parent:
        if local_tag(child.tag) == tag:
            if child.get(XSI_NIL) == "true":
                return None
            text = (child.text or "").strip()
            return text or None
    return None


def iter_member_of_parliament(path: Path) -> Iterator[ET.Element]:
    """Stream <MemberOfParliament> elements without loading full tree."""
    for event, elem in ET.iterparse(path, events=("end",)):
        if local_tag(elem.tag) == "MemberOfParliament":
            yield elem
            elem.clear()


@dataclass
class WalkContext:
    heading: dict[int, str | None] = field(default_factory=lambda: {1: None, 2: None, 3: None})
    section_label: int | None = None
    subsection_label: str | None = None
    paragraph_label: str | None = None
    seen_terms: set[str] = field(default_factory=set)


def walk(
    node: ET.Element,
    ctx: WalkContext,
    path: tuple[str, ...],
) -> Iterator[dict]:
    tag = local_tag(node.tag)
    path = path + (tag,)

    if path == ("Bill",):
        ident = node.find("Identification")
        stages = node.find(".//Stages")
        yield {
            "_row_class": "ByLawDocumentRow",
            "long_title": child_text(ident, "LongTitle") if ident is not None else None,
            "running_head": child_text(ident, "RunningHead") if ident is not None else None,
            "bill_origin": node.get("bill-origin"),
            "bill_type": node.get("bill-type"),
            "lang": node.get("lang"),
            "stage": stages.get("stage") if stages is not None else None,
            "doc_date_time": node.get("date-time"),
        }

    elif path_suffix(path, 2) == ("Body", "Heading"):
        level = int(node.get("level"))
        ctx.heading[level] = child_text(node, "TitleText")
        for deeper in range(level + 1, 4):
            ctx.heading[deeper] = None

    elif path_suffix(path, 2) == ("Body", "Section"):
        ctx.section_label = parse_section_label(child_text(node, "Label"))
        ctx.subsection_label = None
        ctx.paragraph_label = None
        yield {
            "_row_class": "ByLawSectionRow",
            "section_label": ctx.section_label,
            "marginal_note": child_text(node, "MarginalNote"),
            "text": child_text(node, "Text"),
            "heading_lv1": ctx.heading[1],
            "heading_lv2": ctx.heading[2],
            "heading_lv3": ctx.heading[3],
        }

    elif path_suffix(path, 2) == ("Section", "Subsection"):
        ctx.subsection_label = child_text(node, "Label")
        ctx.paragraph_label = None
        yield {
            "_row_class": "ByLawSubsectionRow",
            "section_label": ctx.section_label,
            "subsection_label": ctx.subsection_label,
            "text": child_text(node, "Text"),
            "marginal_note": child_text(node, "MarginalNote"),
        }

    elif path_suffix(path, 1) == ("Definition",):
        term_en = node.findtext("Text/DefinedTermEn")
        if term_en and term_en not in ctx.seen_terms:
            ctx.seen_terms.add(term_en)
            yield {
                "_row_class": "ByLawDefinedTermRow",
                "term_en": term_en,
                "term_fr": node.findtext("Text/DefinedTermFr"),
                "defined_in_section_label": ctx.section_label,
                "defined_in_subsection_label": ctx.subsection_label,
                "text": child_text(node, "Text"),
            }
            text_elem = node.find("Text")
            if text_elem is not None:
                for ref in text_elem.iter("DefinitionRef"):
                    cited = (ref.text or "").strip()
                    if cited:
                        yield {
                            "_row_class": "ByLawTermCrossRefRow",
                            "source_term_en": term_en,
                            "cited_term_en": cited,
                            "cited_in_section_label": ctx.section_label,
                            "cited_in_subsection_label": ctx.subsection_label,
                        }

    elif path_suffix(path, 2) in (("Section", "Paragraph"), ("Subsection", "Paragraph")):
        ctx.paragraph_label = child_text(node, "Label")
        yield {
            "_row_class": "ByLawParagraphRow",
            "section_label": ctx.section_label,
            "subsection_label": ctx.subsection_label,
            "paragraph_label": ctx.paragraph_label,
            "text": child_text(node, "Text"),
        }

    elif path_suffix(path, 1) == ("Subparagraph",):
        yield {
            "_row_class": "ByLawSubParagraphRow",
            "section_label": ctx.section_label,
            "subsection_label": ctx.subsection_label,
            "paragraph_label": ctx.paragraph_label,
            "subparagraph_label": child_text(node, "Label"),
            "text": child_text(node, "Text"),
        }

    elif tag == "DefinitionRef" and "Definition" not in path:
        cited = (node.text or "").strip()
        if cited:
            yield {
                "_row_class": "ByLawTermCrossRefRow",
                "source_term_en": None,
                "cited_term_en": cited,
                "cited_in_section_label": ctx.section_label,
                "cited_in_subsection_label": ctx.subsection_label,
            }

    elif tag == "XRefExternal":
        reference_name = (node.text or "").strip()
        if reference_name:
            yield {
                "_row_class": "ByLawExternalRefRow",
                "reference_name": reference_name,
                "reference_type": node.get("reference-type"),
                "cited_in_section_label": ctx.section_label,
                "cited_in_subsection_label": ctx.subsection_label,
            }

    for child in node:
        yield from walk(child, ctx, path)
