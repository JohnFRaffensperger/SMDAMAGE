# LocalHTML.py | Simple HTML table generation utility for table_to_html.py.

def _escape(val):
	s = '' if val is None else str(val)
	return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def table(rows, header_row=None):
	"""Return an HTML table string from a list of rows (tuples/lists).
	Optionally include a header_row list of column names."""
	parts = ['<table border="1" cellpadding="3" cellspacing="0">']
	if header_row:
		parts.append('<tr>' + ''.join(f'<th>{_escape(h)}</th>' for h in header_row) + '</tr>')
	for row in rows:
		parts.append('<tr>' + ''.join(f'<td>{_escape(v)}</td>' for v in row) + '</tr>')
	parts.append('</table>')
	return '\n'.join(parts)

class Table:
	"""HTML table object. str(Table(rows, header_row=...)) returns the HTML string."""
	def __init__(self, rows, header_row=None):
		self._html = table(rows, header_row=header_row)
	def __str__(self):
		return self._html
