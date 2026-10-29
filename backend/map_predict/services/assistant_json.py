"""Decode provider envelopes without rendering internal JSON as chat text."""
import json
import re
from itertools import islice

LIST_FIELDS = ('sources', 'edits', 'scores', 'table_edits')
INTERNAL_FIELDS = {'filters', 'metadata', 'page_content', 'documents', 'tool_calls',
                   'so_tieu_chi', 'ten_tieu_chi', 'phan_nhom', 'loai_noi_dung',
                   'phuong_phap_gis', 'nhom_diem', 'source_ref', 'record_id'}


def text_content(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict) and item.get('type') in ('thinking', 'reasoning', 'redacted_thinking'):
                continue
            if not isinstance(item, dict) or item.get('type') not in ('text', 'output_text') or not isinstance(item.get('text'), str):
                raise ValueError('Provider content must be text')
            parts.append(item['text'])
        if parts:
            return '\n'.join(parts)
    raise ValueError('Provider content must be text')


def json_object(value):
    """Allow fences/prose, but reject ambiguous objects and malformed JSON."""
    text = text_content(value).strip().lstrip('\ufeff')
    if len(text) > 500000:
        raise ValueError('Model output exceeded limit')
    fence = re.fullmatch(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.I)
    if fence:
        text = fence[1].strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        if text.startswith(('{', '[')):
            raise ValueError('Incomplete JSON output') from None
        # A single complete object with optional narration around it.
        candidates, offset = [], 0
        decoder = json.JSONDecoder()
        for match in islice(re.finditer(r'\{', text), 64):
            if match.start() < offset:
                continue
            try:
                item, end = decoder.raw_decode(text, match.start())
                offset = end
                if isinstance(item, dict):
                    candidates.append((item, match.start(), end))
            except json.JSONDecodeError:
                continue
        if len(candidates) != 1:
            raise ValueError('Expected a single JSON object') from None
        result, start, end = candidates[0]
        if re.search(r'[{}\[\]]', text[:start] + text[end:]):
            raise ValueError('Ambiguous JSON envelope')
    for _ in range(2):
        if not isinstance(result, str):
            break
        result = json.loads(result)
    if not isinstance(result, dict):
        raise ValueError('Expected a JSON object')
    return result


def model_result(content):
    result = json_object(content)
    for _ in range(3):
        if 'answer' in result:
            break
        nested = next((result[key] for key in ('result', 'data', 'response')
                       if key in result and isinstance(result[key], (str, dict))), None)
        if nested is None:
            break
        result = nested if isinstance(nested, dict) else json_object(nested)
    # Some compatible providers serialize the whole result inside answer.
    answer = result.get('answer')
    if isinstance(answer, str) and answer.lstrip().startswith(('{', '```json')):
        try:
            nested = json_object(answer)
        except ValueError:
            nested = None
        if isinstance(nested, dict) and isinstance(nested.get('answer'), str):
            if any(result.get(key) for key in LIST_FIELDS) or result.get('create_table'):
                raise ValueError('Conflicting nested action plans')
            result = nested
        elif isinstance(nested, dict) and set(nested) & INTERNAL_FIELDS:
            raise ValueError('Internal retrieval JSON is not a display answer')
    if not isinstance(result.get('answer'), str):
        raise ValueError('Missing text answer')
    if any(not isinstance(result.get(key, []), list) for key in LIST_FIELDS):
        raise ValueError('Invalid action lists')
    return result
