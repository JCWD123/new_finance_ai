import json
import re
from collections import Counter
from collections import defaultdict
from typing import List


def split_think_and_json(raw_data: str) -> tuple[str, str]:
    # 提取JSON部分
    json_match = re.search(r"```json\n(.*?)\n```", raw_data, re.DOTALL)
    json_str = (
        json_match.group(1).strip()
        if json_match
        else re.search(r"{.*}", raw_data, re.DOTALL).group(0).strip()
    )
    try:
        json_part = json.loads(json_str)
    except json.decoder.JSONDecodeError:
        json_part = json.loads(
            json_str.replace(" ", "")
            .replace("{\n", "{")
            .replace("\n}", "}")
            .replace("\n", "\\n")
        )

    # 提取思考部分（JSON标记之前的所有内容）
    think_part = (
        raw_data[: json_match.start()]
        if json_match
        else raw_data[: re.search(r"{.*}", raw_data, re.DOTALL).start()]
    )
    # 清理思考部分：去除头尾空白和特定标记
    think_part = think_part.strip().lstrip("</think>\n").rstrip("\n<think>").strip()

    return think_part, json_part


def extract_square_bracket_contents(data: List[dict]) -> tuple[str, List[dict]]:
    """
    提取数据中【】包含的内容

    参数：
    data -- List[dict]，数据

    返回：
    包含所有提取内容的列表
    """
    results = []
    posts = []

    # 正则表达式模式：匹配中文方括号及其中内容
    pattern = re.compile(r"(【[^】]*】)")

    for item in data:
        content = item.get("mes", "")
        match = pattern.search(content)
        if match:
            # 提取第一个匹配组内容并去除前后空白
            result = match.group(1).strip()
            results.append(result)
        else:
            result = ""
        item["mes"] = content.replace(result, "")
        posts.append(item)
    counter = Counter(results)

    return max(counter, key=counter.get) if counter else "", posts


def generate_hot_words(words):
    """高频热词统计函数"""
    term_freq = defaultdict(int)
    # 遍历所有文本的词频列表
    for sublist in words:
        for term_dict in sublist:
            term = term_dict["term"]
            freq = term_dict["frequency"]
            term_freq[term] += freq

    # 按总词频降序排序，取前10
    sorted_terms = sorted(term_freq.items(), key=lambda x: (-x[1], x[0]))[:10]
    return [{"term": term, "total_frequency": freq} for term, freq in sorted_terms]


def generate_hot_sectors(sectors):
    """行业板块分析函数"""
    sector_counter = defaultdict(int)
    total_docs = len(sectors)

    # 语义清洗和合并规则
    def process_sector(sector):
        # 去除括号及内容
        clean = re.sub(r"[（）()].*?[）)]", "", sector)
        # 后缀合并（按优先级排序）
        clean = re.sub(r"行业$|产业$|金融$|业$", "", clean)
        return clean.strip()

    # 统计处理后的行业
    for doc_sectors in sectors:
        seen = set()  # 单文档去重
        for sector in doc_sectors:
            processed = process_sector(sector)
            if processed not in seen:
                sector_counter[processed] += 1
                seen.add(processed)

    # 计算热力值并排序
    hotness = [
        (sector, round(count / total_docs * 100, 1))
        for sector, count in sector_counter.items()
        if count > 1  # 过滤低频项
    ]
    sorted_sectors = sorted(hotness, key=lambda x: (-x[1], x[0]))

    return [{"term": s, "hotness": h} for s, h in sorted_sectors]


def process_text(text: str, domain: str = None) -> str:
    text = re.sub(
        r"（(?:.*?评分|字数统计)[:：]?\s*\d+\.?\d*[\u4e00-\u9fa5]*）", "", text
    )
    text = re.sub("【.*?】", "", text.strip())
    text = re.sub(r"\s*[$（【][总]?字数\s*：\s*\d+[\s字]*[$）】]\s*$", "", text)
    text = re.sub("<无法溯源事件ID>", "", text)
    text = re.sub("<行情校验>", "", text)
    text = re.sub(r"<\d{4}-\d{2}-\d{2} \d{2}:\d{2}>", "", text)
    text = text.replace("\n", "<br/>")
    if domain is not None:
        text = domain + text.strip()
    return text


def remove_sensitive_information(text) -> list:
    pattern = r"\b(?:Xi\s*Jinping|Xi(?:\s+|$)|Jinping|XiJinping)\b"
    if isinstance(text, dict):
        text["mes"] = re.sub(pattern, "Leader", text["mes"], flags=re.IGNORECASE)
    else:
        text = re.sub(pattern, "Leader", text, flags=re.IGNORECASE)

    return text
