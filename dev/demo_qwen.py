import torch
from qwen_asr import Qwen3ASRModel
from time import time

model = Qwen3ASRModel.from_pretrained(
    "Qwen/Qwen3-ASR-0.6B",
    dtype=torch.bfloat16,
    device_map="cuda:0",
    # attn_implementation="flash_attention_2",
    # Batch size limit for inference. -1 means unlimited. Smaller values can help avoid OOM.
    max_inference_batch_size=32,
    # Maximum number of tokens to generate. Set a larger value for long audio input.
    max_new_tokens=1024,
)

time_start = time()
results = model.transcribe(
    # Audio input(s) Support:
    # - str: local path / URL / base64 data url
    # - (np.ndarray, sr)
    # - list of above
    audio="dev/short.wav",
    language=None, # set "Japanese" to force the language
)
time_end = time()

# Should be "Japanese"
print(results[0].language)
# Should be "週明けからまた挨拶運動を始めようと思うのは、せっかく新しいメンバーが加わったわけだし。"
print(results[0].text)

print(f"Time elapsed: {time_end - time_start:.2f} seconds")