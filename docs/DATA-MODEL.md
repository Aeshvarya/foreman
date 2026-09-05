# Foreman — Data Model

The graph schema, what backs it, and what has to change for real project data.

## Two representations of the same graph

**Neo4j is the source of truth.** The CPM math runs on an in-memory NetworkX
mirror rebuilt from Neo4j, so the scheduling engine is unchanged whether or not
a database is present.

```
project.json --load_to_neo4j--> Neo4j --graph_from_neo4j--> NetworkX --> CPM
```

If `NEO4J_URI` is unset, `get_graph()` falls back to building straight from
project JSON. Same schema, same engine, no database required — useful for tests
and for running the reasoning layer without infrastructure.

## Node labels

```cypher
(:Project  {name, handover, description})

(:Supplier {id, name, location, reliability})

(:Material {id, name, supplier, po, submittal_status, fabrication_status,
            shipment_status, roj_date, confidence, source, ...})

(:Activity {id, name, duration_days, depends_on, needs_materials, early_start})
```

Every node also carries `kind` (`supplier` / `material` / `activity`), which is
what the NetworkX layer dispatches on.

## Relationships

```cypher
(:Supplier)-[:SUPPLIES        {confidence}]->(:Material)
(:Material)-[:FEEDS_ACTIVITY  {roj_date, confidence}]->(:Activity)
(:Activity)-[:DEPENDS_ON      {confidence}]->(:Activity)   // prerequisite -> dependent
```

**Edge direction follows the flow of consequence.** A delay travels
`supplier → material → activity → dependent activities → handover`, so the
blast radius of any node is just its descendants.

> ⚠️ Note the naming difference: the relationship is `FEEDS_ACTIVITY` in Neo4j
> and `kind="feeds"` on the NetworkX edge. Same edge, two names.

## The fields that carry the reasoning

| Field | On | Why it matters |
|---|---|---|
| `confidence` | materials, all edges | Drives the confidence ladder, Monte Carlo spread, and whether a fact is acted on or flagged for a human |
| `source` | materials | Where the fact came from; `kg_builder` resolves conflicts by source weight |
| `roj_date` | materials, FEEDS edges | Required-on-job date — the arrival constraint the forward pass schedules against |
| `duration_days` | activities | CPM duration |
| `depends_on` | activities | Prerequisite activities |
| `needs_materials` | activities | Which materials gate this activity |
| `reliability` | suppliers | Feeds the alternate-supplier capability vector |

**`confidence` is the field to understand first.** A 0.99 material barely moves
in simulation and is acted on directly; a 0.6 material swings wide and gets
flagged for human review. It is what makes the output safe to show a client.

## Useful queries

```cypher
// Everything downstream of an activity (the blast radius)
MATCH (x:Activity)-[:DEPENDS_ON*]->(d:Activity) RETURN d

// Everything upstream of an activity
MATCH (p:Activity)-[:DEPENDS_ON*]->(x:Activity) RETURN p

// Every activity a given material touches
MATCH (m:Material)-[*]->(a:Activity) WHERE m.id = 'MAT-x' RETURN DISTINCT a
```

## Loading

`load_to_neo4j()` **wipes the database first** (`MATCH (n) DETACH DELETE n`),
then writes Project, Suppliers, Materials, Activities and their edges from the
active project file.

This is single-project, destructive-load by design — a demo pattern, not a
production one. See "What has to change" below.

CLI: `python -m src.db --load` · `python -m src.db --verify`

## Current scale

The deployed demo graph holds **26 nodes** for one synthetic project
("Sunrise DC-1", a 12MW data centre in Jaipur):

```
6 suppliers · 8 materials · 12 activities · 29 edges
```

## What has to change for real project data

Honest list, for the architecture conversation:

1. **Multi-project isolation.** `load_to_neo4j` wipes the whole database and
   loads one project. Real use needs project scoping — a label, a property, or
   separate databases. This is the biggest single gap, and it interacts
   directly with Kaya's org-per-schema Postgres model.

2. **No org/tenant concept.** Nothing in the schema knows about organisations.
   Whatever scoping Kaya uses has to be added here.

3. **P6 ingest.** The graph is built from Foreman's own project JSON. Nothing
   has been tested against real P6 output — expect nulls, duplicate IDs and
   activity naming that doesn't match current assumptions.

4. **`category_of()` is string-matching on material names**
   (`alt_supplier.py`). It works because the synthetic dataset was written to
   match. Real vendor material names will not match, and alternate-supplier
   recommendations will silently return nothing. **This is the single most
   likely thing to break on first contact with real data** — it already caused
   a near-miss the day before the hackathon final.

5. **Scale.** 30–40 critical-path items out of ~3,000 is one to two orders of
   magnitude above anything this has run on. Graph build time and cascade
   traversal depth are both untested there.

6. **No indexes or constraints.** No uniqueness constraint on `id`, no indexes.
   Fine at 26 nodes, not fine later.
