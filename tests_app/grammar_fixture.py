"""Authored standalone examples for the seven visual grammars, never video summaries."""
from pathlib import Path
from distill.models import PresentationPlan, Relationship, Visual
from distill.renderer import render_page
from tests_app.learning_fixture import fixture


def build(root=Path('.feasibility/grammar-fixtures')):
    root.mkdir(parents=True, exist_ok=True)
    for grammar in ['concept_map', 'causal_graph', 'process', 'argument_map', 'hierarchy', 'comparison', 'timeline']:
        source, knowledge, _ = fixture('en')
        source.title = f'Authored {grammar} fixture; not a real video summary'
        node_ids, relationships = ['u1', 'u2', 'u3', 'u4'], ['r1']
        if grammar == 'causal_graph':
            knowledge.units[0].title = 'Greater heat exposure'
            knowledge.units[0].summary = 'Heat exposure is a process input.'
            knowledge.units[1].title = 'Reaction speed'
            knowledge.units[1].summary = 'Greater heat increases reaction speed.'
            knowledge.units[1].explanation = source.snippets[0].text
            knowledge.units[1].evidence = knowledge.units[0].evidence
            knowledge.units[1].child_ids = []
            knowledge.units[1].caveats = []
            knowledge.relationships[0] = Relationship(id='r1', source='u1', target='u2', label='increases reaction speed', kind='causes', evidence=knowledge.units[0].evidence)
            node_ids = ['u1', 'u2']
        elif grammar == 'process':
            knowledge.units[0].title = 'Apply heat'
            knowledge.units[3].title = 'Observe color and stop'
            knowledge.relationships[0] = Relationship(id='r1', source='u1', target='u4', label='before observation', kind='precedes', evidence=knowledge.units[3].evidence)
            node_ids = ['u4', 'u1']  # Intentionally reversed: renderer must follow the relation.
        elif grammar == 'argument_map':
            knowledge.units[1].kind = 'claim'
            knowledge.units[4].kind = 'objection'
            node_ids, relationships = ['u2', 'example'], []
        elif grammar == 'hierarchy':
            node_ids, relationships = ['u2', 'example'], []
        elif grammar == 'comparison':
            node_ids, relationships = ['u2', 'u3'], []
        elif grammar == 'timeline':
            node_ids, relationships = [], []
        view = Visual(id='test-view', type=grammar, title=grammar.replace('_', ' ').title(), reader_question='Explore this authored example and inspect its source.', rationale='Deterministic renderer verification', node_ids=node_ids, relationship_ids=relationships, section_ids=[s.id for s in knowledge.sections] if grammar == 'timeline' else [])
        plan = PresentationPlan(visuals=[view], reading_order=['test-view'])
        render_page(source, knowledge, plan, root / f'{grammar}.html')


if __name__ == '__main__':
    build()
