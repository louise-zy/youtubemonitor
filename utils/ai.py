import logging
import openai
import httpx
from typing import Optional, Dict, List

class AIContentProcessor:
    """AI内容处理器，用于生成摘要和大纲"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        options: Optional[Dict] = None,
        proxy: Optional[str] = None,
    ):
        self.client = None
        try:
            http_client = None
            if proxy:
                logging.info(f"AI处理器已启用代理: {proxy}")
                http_client = httpx.Client(proxies=proxy)
                
            self.client = openai.OpenAI(
                api_key=api_key, 
                base_url=base_url,
                http_client=http_client
            )
        except Exception as e:
            logging.warning(f"OpenAI客户端初始化失败: {e}")
            
        self.model = model
        self.options = options or {}
        
        # 分块配置
        self.enable_chunking = self.options.get("enable_chunking", True)
        self.chunk_char_limit = int(self.options.get("chunk_char_limit", 5000))
        self.chunk_overlap = int(self.options.get("chunk_overlap", 400))
        self.max_chunks = max(1, int(self.options.get("max_chunks", 6)))
        self.chunk_summary_max_tokens = int(self.options.get("chunk_summary_max_tokens", 600))
        self.final_summary_max_tokens = int(self.options.get("final_summary_max_tokens", 1000))
        self.temperature = float(self.options.get("temperature", 0.7))

    def generate_summary_and_outline(self, title: str, content: str) -> Dict[str, str]:
        """生成摘要和大纲"""
        if not self.client:
            return {
                "summary": "AI摘要功能不可用：OpenAI客户端未初始化",
                "outline": "AI大纲功能不可用：OpenAI客户端未初始化",
            }

        cleaned = (content or "").strip()
        if not cleaned:
            return {
                "summary": "没有可用内容，无法生成摘要",
                "outline": "没有可用内容，无法生成大纲",
            }

        try:
            chunks = self._split_into_chunks(cleaned)
            if len(chunks) == 1 or not self.enable_chunking:
                return self._parse_response(self._run_single_pass(title, chunks[0]))

            chunk_summaries = self._summarize_chunks(title, chunks)
            return self._parse_response(self._build_final_summary(title, chunk_summaries))
        except Exception as exc:
            logging.error("生成摘要失败: %s", exc)
            return {
                "summary": f"生成摘要失败: {str(exc)}",
                "outline": f"生成大纲失败: {str(exc)}",
            }

    def _run_single_pass(self, title: str, content: str) -> str:
        prompt = (
            "请对以下内容进行分析和总结。\n\n"
            f"标题：{title}\n\n"
            "正文内容：\n"
            f"{content}\n\n"
            "请提供：\n"
            "1. 详细的中文摘要（300-500字）\n"
            "2. 结构化的内容大纲（要点形式）\n\n"
            "请用中文回复，格式如下：\n"
            "【摘要】\n"
            "（这里写摘要内容）\n\n"
            "【大纲】\n"
            "1. 主要观点一\n"
            "2. 主要观点二\n"
            "3. 主要观点三\n"
            "..."
        )
        messages = [
            {"role": "system", "content": "你是一个专业的内容分析师，擅长总结和分析内容"},
            {"role": "user", "content": prompt},
        ]
        return self._call_model(messages, self.final_summary_max_tokens)

    def _summarize_chunks(self, title: str, chunks: List[str]) -> List[str]:
        summaries: List[str] = []
        total = min(len(chunks), self.max_chunks)
        for idx, chunk in enumerate(chunks[: self.max_chunks], 1):
            prompt = (
                f"你正在处理长内容的第{idx}/{total}段，请用中文概括这一段的关键信息（80-120字），保留专有名词和数据。\n\n"
                f"标题：{title}\n\n"
                f"当前段落：\n{chunk}"
            )
            messages = [
                {"role": "system", "content": "你是一个专业的内容分析师，擅长总结和分析内容"},
                {"role": "user", "content": prompt},
            ]
            summary = self._call_model(messages, self.chunk_summary_max_tokens)
            summaries.append(f"第{idx}段：{summary.strip()}")
        return summaries

    def _build_final_summary(self, title: str, chunk_summaries: List[str]) -> str:
        combined = "\n".join(chunk_summaries)
        prompt = (
            "请根据以下分段摘要，综合生成整个内容的完整中文摘要（400字左右）以及结构化内容大纲。\n\n"
            f"标题：{title}\n\n"
            f"分段摘要：\n{combined}\n\n"
            "请用与单段摘要相同的输出格式：\n"
            "【摘要】...\n"
            "【大纲】..."
        )
        messages = [
            {"role": "system", "content": "你是一个专业的内容分析师，擅长总结和分析内容"},
            {"role": "user", "content": prompt},
        ]
        return self._call_model(messages, self.final_summary_max_tokens)

    def _split_into_chunks(self, text: str) -> List[str]:
        if not text:
            return [""]
        chunk_size = max(1000, self.chunk_char_limit)
        overlap = max(0, min(self.chunk_overlap, chunk_size // 2))
        chunks: List[str] = []
        start = 0
        length = len(text)
        while start < length and len(chunks) < self.max_chunks:
            end = min(length, start + chunk_size)
            chunks.append(text[start:end])
            if end >= length:
                break
            start = max(end - overlap, 0)
        if start < length and len(chunks) < self.max_chunks:
            chunks.append(text[start:])
        return chunks or [text]

    def _call_model(self, messages: List[Dict[str, str]], max_tokens: int) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=self.temperature,
        )
        return response.choices[0].message.content.strip()

    def _parse_response(self, content: str) -> Dict[str, str]:
        summary = ""
        outline = ""
        if "【摘要】" in content and "【大纲】" in content:
            parts = content.split("【大纲】")
            summary = parts[0].replace("【摘要】", "").strip()
            outline = (parts[1] if len(parts) > 1 else "").strip()
        else:
            summary = content.strip()
            outline = "未能生成结构化大纲"
        return {
            "summary": summary,
            "outline": outline,
        }
