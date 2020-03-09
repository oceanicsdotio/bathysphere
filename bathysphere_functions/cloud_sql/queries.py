from datetime import datetime
from json import dumps
from typing import Any, Callable
from decimal import Decimal
from collections import namedtuple
from attrs import attr
from enum import Enum


class PostgresType(Enum):
    Numerical = "DOUBLE PRECISION NULL"
    TimeStamp = "TIMESTAMP NOT NULL"
    Geography = "GEOGRAPHY NOT NULL"
    IntIdentity = "INT PRIMARY KEY"
    NullString = "VARCHAR(100) NULL"

@attr.s
class Coordinates:
    x: float = attr.ib()
    y: float = attr.ib()

@attr.s
class Field:
    value: Any = attr.ib()
    type: str = attr.ib()

@attr.s
class Query:
    sql: str = attr.ib()
    parser: Callable = attr.ib()

@attr.s
class Distance:
    value: float = attr.ib()
    unit: str = attr.ib()

@attr.s
class Schema:
    fields: [Field] = attr.ib(default=attr.Factory(list))

@attr.s
class Table:
    name: str = attr.ib()
    schema: Schema = attr.ib(default=Schema())





def parsePostgresValueIn(v: Any) -> str:
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, float):
        return str(v)
    if isinstance(v, int):
        return f"{v}.0"
    if isinstance(v, str):
        return f"'{v}'"
    if isinstance(v, dict):
        return f"ST_GeomFromGeoJSON('{dumps(v)}')"
    return "NULL"


def parsePostgresValueOut(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    return v

def join(x: str) -> str:
        return ", ".join(x)

def declareTable(table: Table) -> Query:
    queryString = f"""
    CREATE TABLE IF NOT EXISTS {table}({join(f'{f.value} {f.type}' for f in table.schema)});
    """
    return Query(queryString, None)


def insertRecords(
    table: Table,  
    data: ()
) -> Query:
    """
    Insert new rows into database.
    """
    _parsedValues = (f"({join(map(parsePostgresValueIn, row))})" for row in data)
    columns, values = map(join, ((field[0] for field in table.schema), _parsedValues))

    queryString = f"""
    INSERT INTO {table.name} ({columns}) VALUES {values};
    """
    return Query(queryString, None)



def selectRecords(
    table: Table, 
    order_by: str = None, 
    limit: int = 100, 
    fields: (str, ) = ("*",), 
    order: str ="DESC", 
    conditions=()
) -> Query:
   
    """
    Read back values/rows.
    """
    _order = f"ORDER BY {order_by} {order}" if order_by else ""
    _conditions = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    queryString = f"""
    SELECT {', '.join(fields)} FROM {table} {_conditions} {_order} LIMIT {limit};
    """
    return Query(queryString, None)


def nearestNeighbor(
    coordinates: Coordinates, 
    kNeighbors: int, 
    searchRadius: Distance,
) -> Query:
    """
    Format the query and parser required for making k nearest neighbor
    queries to a database running PostGIS, with the appropriate
    spatial indices already in place.
    """

    x, y = coordinates
    targetTable = "landsat_points"
    targetColumn, alias = "oyster_suitability_index", "osi"

    queryString = f"""
    SELECT AVG({alias}), COUNT({alias}) FROM (
        SELECT {alias} FROM (
            SELECT {targetColumn} as {alias}, geo
            FROM {targetTable}
            ORDER BY geo <-> 'POINT({x} {y})'
            LIMIT {kNeighbors}
        ) AS knn
        WHERE st_distance(geo, 'POINT({x} {y})') < {searchRadius}
    ) as points;
    """

    def parser(fetchAll):

        avg, count = fetchAll[0]
        return {
            "message": "Mean Oyster Suitability",
            "value": {
                "mean": avg,
                "distance": {
                    "value": searchRadius,
                    "units": "meters"
                },
                "observations": {
                    "requested": kNeighbors,
                    "found": count
                }
            }
        }

    return queryString, parser

