"""ko-sroberta를 ONNX로 내보내고 8비트로 줄입니다. (GitHub Actions의 export-model 워크플로가 실행)

  python scripts/export_onnx.py --out onnx_model
결과: onnx_model/model.onnx (8비트), onnx_model/tokenizer.json
그리고 원래 모델과 문장 벡터가 얼마나 같은지(코사인)를 출력합니다.
"""
import argparse
import csv
from pathlib import Path

import numpy as np
import torch
from onnxruntime.quantization import QuantType, quantize_dynamic
from sentence_transformers import SentenceTransformer
from transformers import AutoModel, AutoTokenizer

NAME = "jhgan/ko-sroberta-multitask"


class Wrap(torch.nn.Module):
    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, input_ids, attention_mask):
        return self.m(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="onnx_model")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    tok = AutoTokenizer.from_pretrained(NAME)
    bt = tok.backend_tokenizer
    bt.enable_padding(pad_id=tok.pad_token_id, pad_token=tok.pad_token)
    bt.enable_truncation(128)
    bt.save(str(out / "tokenizer.json"))
    model = AutoModel.from_pretrained(NAME).eval()
    x = tok(["자기소개서 지원동기 쓰는 법"], return_tensors="pt")
    fp32 = out / "model_fp32.onnx"
    torch.onnx.export(Wrap(model), (x["input_ids"], x["attention_mask"]), str(fp32),
                      input_names=["input_ids", "attention_mask"], output_names=["last_hidden_state"],
                      dynamic_axes={"input_ids": {0: "b", 1: "s"}, "attention_mask": {0: "b", 1: "s"},
                                    "last_hidden_state": {0: "b", 1: "s"}},
                      opset_version=17, dynamo=False)
    quantize_dynamic(str(fp32), str(out / "model.onnx"), weight_type=QuantType.QInt8)
    fp32.unlink()
    for p in out.glob("*.data"):
        p.unlink()
    print("model.onnx", round((out / "model.onnx").stat().st_size / 1e6, 1), "MB")

    # 원래 모델과 비교
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from chatbot.onnx_encoder import OnnxEncoder

    with open(Path(__file__).resolve().parent.parent / "tests/test_questions_200.csv", encoding="utf-8-sig") as f:
        qs = [r["query"] for r in csv.DictReader(f)]
    A = SentenceTransformer(NAME).encode(qs, normalize_embeddings=True)
    B = OnnxEncoder(out).encode(qs)
    cos = (A * B).sum(1)
    print(f"원래 모델 대비 코사인: 평균 {cos.mean():.4f}, 최소 {cos.min():.4f}")


if __name__ == "__main__":
    main()
