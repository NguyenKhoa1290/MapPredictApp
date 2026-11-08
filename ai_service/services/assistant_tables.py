"""Bounded CSV editing proposals, using original row indexes until apply completes."""
import math
import re

from .assistant_sources import normalized


def edit_state(scores):
    return {'deleted_columns': set(), 'deleted_rows': set(),
            'cells': {(item['row_index'], item['column']) for item in scores},
            'edited_rows': {item['row_index'] for item in scores},
            'edited_columns': {item['column'] for item in scores}}


def validate_edit(edit, rows, columns, message, state):
    if not isinstance(edit, dict):
        raise ValueError('Thao tác bảng phải là một đối tượng')
    operation = edit.get('operation')
    if operation not in ('set_cell', 'delete_row', 'delete_column'):
        raise ValueError('Chỉ hỗ trợ sửa ô, xóa hàng và xóa cột')
    clean = {'operation': operation, 'reason': str(edit.get('reason', ''))[:1000]}
    column, index = edit.get('column'), edit.get('row_index')
    if operation != 'delete_row':
        if not isinstance(column, str) or column not in columns:
            raise ValueError('Cột chưa có trong bảng đang nạp')
        clean['column'] = column
    if operation != 'delete_column':
        if type(index) is not int or not 0 <= index < len(rows):
            raise ValueError('Dòng không tồn tại trong bảng đang nạp')
        clean['row_index'] = index
    deleted_columns = state['deleted_columns']
    deleted_rows = state['deleted_rows']
    cells = state['cells']
    if operation == 'delete_column':
        if column in deleted_columns or column in state['edited_columns']:
            raise ValueError('Xóa cột trùng hoặc xung đột với sửa ô, chấm điểm')
        if not [key for key in columns if key not in deleted_columns | {column, 'Y'}]:
            raise ValueError('Bảng cần giữ lại ít nhất một cột')
        clean['affected_rows'] = len(rows)
    elif operation == 'delete_row':
        if index in deleted_rows or index in state['edited_rows']:
            raise ValueError('Xóa hàng trùng hoặc xung đột với sửa ô, chấm điểm')
        clean['before'] = rows[index]
    else:
        if column == 'Y':
            raise ValueError('Y chỉ do mô hình dự đoán tạo ra')
        if index in deleted_rows or column in deleted_columns or (index, column) in cells:
            raise ValueError('Sửa ô trùng hoặc xung đột với thao tác khác')
        value = edit.get('value')
        if value is None:
            value = ''
        if type(value) not in (str, int, float, bool) or len(str(value)) > 1000:
            raise ValueError('Giá trị ô phải là văn bản hoặc số, tối đa 1000 ký tự')
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Giá trị số phải hữu hạn')
        # Direct edits are user-supplied values, never a second route for AI scoring.
        quote = edit.get('quote', '')
        if not isinstance(quote, str) or not quote.strip() or normalized(quote) not in normalized(message):
            raise ValueError('Sửa ô cần trích đúng yêu cầu của người dùng')
        if normalized(column) not in normalized(quote):
            raise ValueError('Yêu cầu cần nêu rõ cột được sửa')
        literal = str(value).lower() if type(value) is bool else str(value)
        if literal and not re.search(r'(?<!\w)' + re.escape(normalized(literal)) + r'(?!\w)', normalized(quote)):
            raise ValueError('Giá trị sửa phải được người dùng nêu rõ, chấm điểm tự động phải dùng scores')
        clean.update(value=value, before=rows[index].get(column, ''), quote=quote[:4000])
    if operation == 'delete_column':
        deleted_columns.add(column)
    elif operation == 'delete_row':
        deleted_rows.add(index)
    else:
        cells.add((index, column))
        state['edited_rows'].add(index)
        state['edited_columns'].add(column)
    return clean


def apply_edits(rows, columns, edits):
    deleted_rows = {item['row_index'] for item in edits if item['operation'] == 'delete_row'}
    deleted_columns = {item['column'] for item in edits if item['operation'] == 'delete_column'}
    for item in edits:
        if item['operation'] == 'set_cell':
            rows[item['row_index']][item['column']] = item['value']
    columns = [column for column in columns if column not in deleted_columns]
    return [{column: row.get(column, '') for column in columns}
            for index, row in enumerate(rows) if index not in deleted_rows], columns
