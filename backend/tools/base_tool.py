"""
SatQuery AI — Base Tool Interface
All specialist tools must subclass BaseTool and implement run().
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from backend.schemas.models import ToolResult, ToolStatus


class BaseTool(ABC):
    """
    Abstract base class for all SatQuery AI specialist tools.
    
    Design Principle:
    - The LLM ORCHESTRATES these tools (understands, plans, selects)
    - These tools EXECUTE the actual analysis (detect, classify, fuse, reconstruct)
    - This separation must remain clean
    """

    name: str = "base_tool"
    description: str = "Base tool interface"
    is_demo: bool = True  # All tools are demo/mock in prototype

    @abstractmethod
    def run(self, inputs: Dict[str, Any]) -> ToolResult:
        """
        Execute the tool with given inputs.
        
        Args:
            inputs: Dict containing image data, parameters, and context.
                   Keys vary per tool but always include:
                   - 'images': list of image arrays or base64 strings
                   - 'metadata': list of ImageMetadata dicts
                   - 'params': dict of tool-specific parameters
                   - 'context': dict with analysis session context
        
        Returns:
            ToolResult with status, confidence, result dict, and optional visual.
        """
        ...

    def timed_run(self, inputs: Dict[str, Any]) -> ToolResult:
        """Wraps run() with execution timing."""
        start = time.time()
        result = self.run(inputs)
        result.execution_time_ms = int((time.time() - start) * 1000)
        result.is_demo = self.is_demo
        return result

    def _success(
        self,
        confidence: float,
        result: Dict[str, Any],
        message: str = "",
        visual_output: Optional[str] = None,
        visual_type: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            confidence=confidence,
            result=result,
            message=message,
            visual_output=visual_output,
            visual_type=visual_type,
            metadata=metadata or {},
            is_demo=self.is_demo,
        )

    def _warning(
        self,
        confidence: float,
        result: Dict[str, Any],
        message: str = "",
        visual_output: Optional[str] = None,
        visual_type: Optional[str] = None,
    ) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.WARNING,
            confidence=confidence,
            result=result,
            message=message,
            visual_output=visual_output,
            visual_type=visual_type,
            is_demo=self.is_demo,
        )

    def _error(self, message: str) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            confidence=0.0,
            result={},
            message=message,
            is_demo=self.is_demo,
        )
