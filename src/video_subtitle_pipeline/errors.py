class PipelineError(Exception):
    """面向操作者展示的可处理流水线错误。"""


class DependencyError(PipelineError):
    """外部工具或运行时依赖不可用。"""


class ConfigurationError(PipelineError):
    """配置不完整或不合法。"""


class ValidationError(PipelineError):
    """外部输入或阶段结果不符合不变量。"""


class LLMResponseError(PipelineError):
    """LLM 未返回符合契约的结构化内容。"""
