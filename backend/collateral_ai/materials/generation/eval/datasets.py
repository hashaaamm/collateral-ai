"""LangSmith dataset helpers for material-gen eval."""

from __future__ import annotations


def push_examples(name: str, example_inputs: list[dict]) -> str:
    from langsmith import Client

    client = Client()
    if client.has_dataset(dataset_name=name):
        dataset = client.read_dataset(dataset_name=name)
    else:
        dataset = client.create_dataset(dataset_name=name)
    for example in example_inputs:
        client.create_example(inputs=example, dataset_id=dataset.id)
    return str(dataset.id)
