from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch

from src.exceptions import ASRError, ModelLoadError


@pytest.fixture
def mock_qwen_asr():
    mock_model_cls = MagicMock()
    mock_model_inst = MagicMock()
    mock_result = MagicMock()
    mock_result.text = "  テスト  "
    mock_model_inst.transcribe.return_value = [mock_result]
    mock_model_cls.from_pretrained.return_value = mock_model_inst
    with patch.dict("sys.modules", {"qwen_asr": MagicMock(Qwen3ASRModel=mock_model_cls)}):
        import sys

        sys.modules.pop("src.asr.qwen_asr", None)
        from src.asr.qwen_asr import QwenASR

        yield QwenASR, mock_model_cls, mock_model_inst, mock_result


def test_init_loads_model(mock_qwen_asr):
    QwenASR, mock_model_cls, _, _ = mock_qwen_asr

    asr = QwenASR()

    mock_model_cls.from_pretrained.assert_called_once_with(
        "Qwen/Qwen3-ASR-0.6B",
        dtype=torch.bfloat16,
        device_map="cuda:0",
        max_inference_batch_size=4,
        max_new_tokens=256,
    )
    assert asr._model is not None


def test_transcribe_returns_stripped_text(mock_qwen_asr):
    QwenASR, _, mock_model_inst, _ = mock_qwen_asr

    asr = QwenASR()
    audio = np.zeros(16000, dtype=np.float32)
    result = asr.transcribe(audio)

    assert result == "テスト"
    mock_model_inst.transcribe.assert_called_once_with(audio=(audio, 16000), language="Japanese")


def test_transcribe_empty_audio_returns_empty_string(mock_qwen_asr):
    QwenASR, _, _, _ = mock_qwen_asr

    asr = QwenASR()
    audio = np.zeros(0, dtype=np.float32)
    result = asr.transcribe(audio)

    assert result == ""


def test_transcribe_short_audio_returns_empty_string(mock_qwen_asr):
    QwenASR, _, _, _ = mock_qwen_asr

    asr = QwenASR()
    audio = np.zeros(100, dtype=np.float32)
    result = asr.transcribe(audio)

    assert result == ""


def test_transcribe_model_not_loaded_raises(mock_qwen_asr):
    QwenASR, _, _, _ = mock_qwen_asr

    asr = QwenASR()
    asr._model = None

    with pytest.raises(ASRError, match="ASR model not loaded"):
        asr.transcribe(np.zeros(16000, dtype=np.float32))


def test_init_failure_raises_model_load_error():
    mock_model_cls = MagicMock()
    mock_model_cls.from_pretrained.side_effect = RuntimeError("CUDA not available")

    import sys

    with patch.dict("sys.modules", {"qwen_asr": MagicMock(Qwen3ASRModel=mock_model_cls)}):
        sys.modules.pop("src.asr.qwen_asr", None)
        from src.asr.qwen_asr import QwenASR

        with pytest.raises(ModelLoadError, match="Failed to load ASR model"):
            QwenASR()


def test_transcribe_failure_raises_asr_error(mock_qwen_asr):
    QwenASR, _, mock_model_inst, _ = mock_qwen_asr
    mock_model_inst.transcribe.side_effect = RuntimeError("GPU OOM")

    asr = QwenASR()

    with pytest.raises(ASRError, match="Transcription failed"):
        asr.transcribe(np.zeros(16000, dtype=np.float32))


def test_unload_clears_model(mock_qwen_asr):
    QwenASR, _, _, _ = mock_qwen_asr

    asr = QwenASR()
    assert asr._model is not None

    asr.unload()

    assert asr._model is None
