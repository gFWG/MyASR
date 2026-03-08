from faster_whisper import WhisperModel
from time import time
# 加载turbo模型
# device可选: "cpu", "cuda", "auto"
# compute_type可选: "int8", "int8_float16", "int16", "float16", "float32"
model = WhisperModel("turbo", device="cuda", compute_type="float16")

# 如果使用CPU
# model = WhisperModel("turbo", device="cpu", compute_type="int8")


# 转录音频文件
time_start = time()
segments, info = model.transcribe(
    "dev\\middle.wav",
    language="ja",  # 可选：指定语言加快速度
    beam_size=5,    # 束搜索大小，越大越准确但越慢
    vad_filter=True # 启用VAD过滤静音
)
time_end = time()

# 打印检测到的语言和概率
print(f"检测到的语言: {info.language} (概率: {info.language_probability:.2f})")

# 输出转录结果
for segment in segments:
    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")

print(f"转录耗时: {time_end - time_start:.2f} 秒")