import json
import zipfile
from io import TextIOWrapper
from pathlib import Path
from typing import Union, Literal

import typer
import yaml
from pydantic import BaseModel, field_validator, ConfigDict
from typing_extensions import Annotated


class CypherQuery(BaseModel):
    name: str
    query: str
    description: str | None = None


class ExtendedCypherQuery(CypherQuery):
    model_config = ConfigDict(extra='forbid')

    guid: str
    prebuilt: bool = False
    category: str
    revision: int
    platforms: Union[str, list[str]]
    resources: Union[str, list[str]] | None = None
    acknowledgements: Union[str, list[str]] | None = None

    @field_validator('platforms', mode='after')
    @classmethod
    def platforms_is_list(cls, value: str | list[str]) -> list[str]:
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    @field_validator('resources', mode='after')
    @classmethod
    def resources_is_list(cls, value: str | list[str]) -> list[str]:
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    @field_validator('acknowledgements', mode='after')
    @classmethod
    def acknowledgementsis_list(cls, value: str | list[str]) -> list[str]:
        if value is None:
            return []
        return value if isinstance(value, list) else [value]


app = typer.Typer()


class QueryBundle:
    def __init__(self, queries: list[CypherQuery]):
        self.queries = queries

    @staticmethod
    def load_query(cypher_query: Path,
                   input_format: Literal['yml', 'json'] = 'json') -> ExtendedCypherQuery | CypherQuery:
        model_choices = {
            'yml': ExtendedCypherQuery,
            'json': CypherQuery,
        }
        cypher_model = model_choices[input_format]
        with open(cypher_query, "r") as query_file:
            yaml_obj = yaml.safe_load(query_file) if input_format == "yml" else json.load(query_file)
            return cypher_model(**yaml_obj)

    @classmethod
    def from_path(cls, input_dir: Path, input_format: Literal['yml', 'json'] = 'json') -> "QueryBundle":
        cypher_queries = list(input_dir.rglob(f"*.{input_format}"))
        queries = [
            QueryBundle.load_query(cypher_query, input_format=input_format) for cypher_query in
            cypher_queries
        ]
        return cls(queries)

    def to_json(self, output_file: TextIOWrapper) -> None:
        all_objects = [query.model_dump() for query in self.queries]
        output_file.write(json.dumps(all_objects, indent=2))

    def to_zip(self, output_file: TextIOWrapper) -> None:
        with zipfile.ZipFile(
                file=output_file.name,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
        ) as archive:
            for query in self.queries:
                archive.writestr(
                    zinfo_or_arcname=f"{query.name}.json",
                    data=query.model_dump_json().encode(),
                )


@app.command()
def convert(
        input_dir: Annotated[
            Path,
            typer.Argument(
                exists=True,
                file_okay=True,
                dir_okay=True,
                readable=True,
                resolve_path=True,
            ),
        ],
        output_file: Annotated[typer.FileTextWrite, typer.Argument()],
        output_format: Annotated[
            Literal["json", "zip"],
            typer.Option(help="Format for export (json/zip)"),
        ] = "json",
        input_format: Annotated[
            Literal["yml", "json"],
            typer.Option(help="Cypher query format (yml/json)"),
        ] = "json"
):
    typer.echo(f"Converting queries to {output_format} output")
    cypher_queries = QueryBundle.from_path(input_dir=input_dir, input_format=input_format)

    if output_format == "json":
        cypher_queries.to_json(output_file)

    else:
        cypher_queries.to_zip(output_file)

    typer.echo(
        f"Finished converting {len(cypher_queries.queries)} Cypher queries ({output_format}) to {output_file.name}"
    )


if __name__ == "__main__":
    app()
