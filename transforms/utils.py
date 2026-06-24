from transforms.context import TransformContext
from linkml_runtime.utils.schemaview import SchemaView

def _get_domain_schema(context: TransformContext) -> SchemaView:
    return SchemaView(context.domain_model_path)

def make_bronze_reference
