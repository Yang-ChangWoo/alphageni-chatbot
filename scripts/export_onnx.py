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
    # 양자화 방식 후보 4개를 만들어 두고, compare_encoders.py가 200문항으로 고름 (variants/<이름>/)
    variants = {
        "all_s8": dict(weight_type=QuantType.QInt8),
        "matmul_s8": dict(weight_type=QuantType.QInt8, op_types_to_quantize=["MatMul"]),
        "matmul_u8": dict(weight_type=QuantType.QUInt8, op_types_to_quantize=["MatMul"]),
        "matmul_s8_pc_rr": dict(weight_type=QuantType.QInt8, op_types_to_quantize=["MatMul"],
                                per_channel=True, reduce_range=True),
    }
    for name, kw in variants.items():
        d = out / "variants" / name
        d.mkdir(parents=True, exist_ok=True)
        quantize_dynamic(str(fp32), str(d / "model.onnx"), **kw)
        (d / "tokenizer.json").write_bytes((out / "tokenizer.json").read_bytes())
        print(name, round((d / "model.onnx").stat().st_size / 1e6, 1), "MB")
    fp32.unlink()
    for p in out.glob("*.data"):
        p.unlink()

    # 원래 모델과 비교
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from chatbot.onnx_encoder import OnnxEncoder

    with open(Path(__file__).resolve().parent.parent / "tests/test_questions_200.csv", encoding="utf-8-sig") as f:
        qs = [r["query"] for r in csv.DictReader(f)]
    A = SentenceTransformer(NAME).encode(qs, normalize_embeddings=True)
    for name in variants:
        cos = (A * OnnxEncoder(out / "variants" / name).encode(qs)).sum(1)
        print(f"{name}: 원래 모델 대비 코사인 평균 {cos.mean():.4f}, 최소 {cos.min():.4f}")


if __name__ == "__main__":
    main()
