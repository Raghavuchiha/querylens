import json
import os

import pandas as pd
from datasets import Dataset
from ragas.metrics import answer_relevancy, faithfulness
from ragas import evaluate
from langchain_google_genai import ChatGoogleGenerativeAI
from llm import get_llm
#llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0)
llm = get_llm(temperature=0)

RESULTS_FILE = "evaluation_results.json"  # read by GET /evaluation/metrics


def run_ragas_eval(query, results, answer, reference_answer):
    # Build the eval dataset from YOUR pipeline's output
    data = {
        "user_input": [query],
        "retrieved_contexts": [[r.chunk.text for r in results]],
        "response": [answer.text],
        "reference": [reference_answer],
    }
    dataset = Dataset.from_dict(data)

    eval_results = evaluate(
        dataset=dataset,
        metrics=[answer_relevancy, faithfulness],
        llm=llm,
    )

    print(eval_results)
    df = eval_results.to_pandas()
    print(df)

    # Append this run to the results file so the /evaluation/metrics endpoint has data
    records = df.astype(object).where(df.notna(), None).to_dict(orient="records")
    existing = []
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r") as f:
            existing = json.load(f)
    with open(RESULTS_FILE, "w") as f:
        json.dump(existing + records, f, indent=2, default=str)

    return eval_results