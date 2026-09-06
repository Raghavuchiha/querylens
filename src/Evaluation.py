import pandas as pd
from datasets import Dataset
from ragas.metrics import answer_relevancy, faithfulness
from ragas import evaluate
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0)


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

    return eval_results