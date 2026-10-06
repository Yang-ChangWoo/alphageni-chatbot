"""ko-sroberta를 ONNX(8비트)로 돌리는 인코더. 메모리가 작은 무료 서버(Render 512MB)용.

SentenceTransformer와 같은 방식(토큰 평균 풀링 → L2 정규화)으로 문장 벡터를 만들고,
encode() 사용법도 같게 맞췄습니다. 모델 파일은 scripts/export_onnx.py로 만듭니다.
"""
from pathlib import Path

import numpy as np

MAX_LEN = 128  # jhgan/ko-sroberta-multitask의 max_seq_length


class OnnxEncoder:
    def __init__(self, model_dir):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        d = Path(model_dir)
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tok.enable_truncation(MAX_LEN)
        if self.tok.padding is None:  # export_onnx.py가 저장할 때 넣어 두지만, 없으면 직접 설정
            pad = next((t for t in ("[PAD]", "<pad>") if self.tok.token_to_id(t) is not None), "[PAD]")
            self.tok.enable_padding(pad_id=self.tok.token_to_id(pad) or 0, pad_token=pad)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.sess = ort.InferenceSession(str(d / "model.onnx"), opts, providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.sess.get_inputs()}

    def encode(self, texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False, **_):
        if isinstance(texts, str):
            texts = [texts]
        out = []
        for s in range(0, len(texts), batch_size):
            enc = self.tok.encode_batch(list(texts[s:s + batch_size]))
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            h = self.sess.run(None, feed)[0]                       # (batch, seq, 768)
            m = mask[..., None].astype(np.float32)
            v = (h * m).sum(1) / np.clip(m.sum(1), 1e-9, None)     # 평균 풀링
            if normalize_embeddings:
                v = v / np.clip(np.linalg.norm(v, axis=1, keepdims=True), 1e-12, None)
            out.append(v.astype(np.float32))
            if show_progress_bar:
                print(f"  {min(s + batch_size, len(texts))}/{len(texts)}", flush=True)
        return np.vstack(out)
