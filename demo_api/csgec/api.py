import re
import json
import torch
from flask import request
from nltk import word_tokenize, sent_tokenize

from demo_api.common import create_api
from sgnlp.models.csgec import (
    CSGConfig,
    CSGModel,
    CSGTokenizer,
    download_tokenizer_files,
)

app = create_api(app_name=__name__, model_card_path="model_card/csgec.json")

config = CSGConfig.from_pretrained("https://storage.googleapis.com/sgnlp/models/csgec/config.json")
model = CSGModel.from_pretrained(
    "https://storage.googleapis.com/sgnlp/models/csgec/pytorch_model.bin",
    config=config,
)
download_tokenizer_files(
    "https://storage.googleapis.com/sgnlp/models/csgec/src_tokenizer/",
    "csgec_src_tokenizer",
)
download_tokenizer_files(
    "https://storage.googleapis.com/sgnlp/models/csgec/ctx_tokenizer/",
    "csgec_ctx_tokenizer",
)
download_tokenizer_files(
    "https://storage.googleapis.com/sgnlp/models/csgec/tgt_tokenizer/",
    "csgec_tgt_tokenizer",
)
src_tokenizer = CSGTokenizer.from_pretrained("csgec_src_tokenizer")
ctx_tokenizer = CSGTokenizer.from_pretrained("csgec_ctx_tokenizer")
tgt_tokenizer = CSGTokenizer.from_pretrained("csgec_tgt_tokenizer")

app.logger.info('Model initialization complete.')


@app.route("/predict", methods=["POST"])
def predict():
    req_body = request.get_json()
    text = req_body["text"]

    original_sentences, prepared_inputs = prepare_sentences(text)

    predicted_sentences = []
    for src_text, ctx_text in prepared_inputs:
        src_ids = torch.LongTensor(src_tokenizer(src_text).input_ids).reshape(1, -1)
        ctx_ids = torch.LongTensor(ctx_tokenizer(ctx_text).input_ids).reshape(1, -1)

        predicted_indices = model.decode(src_ids, ctx_ids)[0]
        predicted_sentences += [prepare_output_sentence(tgt_tokenizer.decode(predicted_indices))]

    output = {"output": list(zip(original_sentences, predicted_sentences))}

    return json.dumps(output)


def prepare_sentences(text):
    # tokenize paragraph into sentences
    original_sentences = sent_tokenize(text)
    original_sentences = list(
        map(lambda x: " ".join(word_tokenize(x)), original_sentences)
    )

    output = []
    ctx = []

    for idx, src in enumerate(original_sentences):
        if idx == 0:
            output += [[src, [src]]]
        else:
            output += [[src, ctx]]
        if len(ctx) == 2:
            ctx = ctx[1:]
        ctx += [src]

    output = list(map(lambda x: [x[0], " ".join(x[1])], output))
    original_sentences = list(
        map(
            lambda sent: re.sub(r'\s([?.!,"](?:\s|$))', r"\1", sent), original_sentences
        )
    )
    return original_sentences, output


def prepare_output_sentence(sent):
    sent = sent.replace(",@@ ", ", ")
    sent = sent.replace("@@ ", "")
    sent = sent.replace(" n't", "n't")
    sent = sent.replace(" 'd ", "'d ")
    sent = sent.replace(" 's ", "'s ")
    sent = sent.replace(" 'm ", "'m ")
    sent = sent.replace(" 'll ", "'ll ")
    sent = sent.replace(" 're ", "'re ")
    sent = sent.replace(" 've ", "'ve ")
    sent = re.sub(r'\s([?.!,"](?:\s|$))', r"\1", sent)
    return sent


if __name__ == "__main__":
    app.run()
