"""A module to display HTML content in a window.

Features:
- Supports both HTML and Markdown content
- Markdown to HTML conversion with extended features
- Copy to clipboard functionality
- Responsive web view.
"""

import markdown2
import wx
import wx.html2

VALID_FORMATS = ["html", "markdown"]
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
	<head>
		<meta charset="UTF-8">
		<title>{title}</title>
	</head>
	<body>
		{content}
	</body>
</html>"""


class HtmlViewWindow(wx.Frame):
	"""A window to display HTML content. Converts Markdown to HTML if needed.

	Supported Markdown features:
	- Fenced code blocks
	- Tables
	- Strikethrough
	- HTML-friendly tags
	"""

	def __init__(
		self,
		parent: wx.Window,
		content: str,
		content_format: str,
		title: str = "HTML Message",
	):
		"""Create a new HtmlViewWindow.

		Args:
			parent: Parent window.
			content: Content to display.
			content_format: Format of the content ('html' or 'markdown').
			title: Window title.
		"""
		if content_format not in VALID_FORMATS:
			raise ValueError(
				f"Invalid format: '{content_format}'. Supported formats: {VALID_FORMATS}"
			)

		if content_format == "markdown":
			content = markdown2.markdown(
				content,
				extras=[
					"fenced-code-blocks",
					"tables",
					"strike",
					"tag-friendly",
				],
			)

		content = HTML_TEMPLATE.format(title=title, content=content)
		super().__init__(parent, title=title, size=(800, 600))

		self._content = content
		self._init_ui()

	def _init_ui(self):
		"""Initialize the UI components."""
		panel = wx.Panel(self)

		self._close_button = wx.Button(panel, id=wx.ID_CLOSE)
		self._copy_button = wx.Button(panel, id=wx.ID_COPY)

		self._close_button.Bind(wx.EVT_BUTTON, self._on_close)
		self._copy_button.Bind(wx.EVT_BUTTON, self._on_copy)

		self._web_view = wx.html2.WebView.New(panel)
		self._web_view.Bind(
			wx.html2.EVT_WEBVIEW_LOADED, lambda _: self._web_view.SetFocus()
		)
		self._web_view.SetPage(self._content, "")

		actions_sizer = wx.BoxSizer(wx.HORIZONTAL)
		actions_sizer.AddStretchSpacer()
		actions_sizer.Add(self._copy_button, 0, wx.ALL, 5)
		actions_sizer.Add(self._close_button, 0)

		main_sizer = wx.BoxSizer(wx.VERTICAL)
		main_sizer.Add(actions_sizer, 0, wx.EXPAND)
		main_sizer.Add(self._web_view, 1, wx.EXPAND)

		panel.SetSizer(main_sizer)

	def _on_close(self, event: wx.Event):
		"""Close the window."""
		self.Close()

	def _on_copy(self, event: wx.Event | None = None):
		"""Copy the content to the clipboard."""
		if wx.TheClipboard.Open():
			html_data_object = wx.HTMLDataObject(self._content)
			wx.TheClipboard.SetData(html_data_object)
			wx.TheClipboard.Close()
		else:
			wx.MessageBox(
				"Failed to open the clipboard.", "Error", wx.OK | wx.ICON_ERROR
			)


def show_html_view_window(
	parent: wx.Window,
	content: str,
	content_format: str = "markdown",
	title: str = "HTML Message",
):
	"""Display an HTML message window.

	Args:
		parent: Parent window.
		content: Content to display.
		content_format: Format of the content ('html' or 'markdown').
		title: Window title.
	"""
	window = HtmlViewWindow(parent, content, content_format, title)
	window.Show()
