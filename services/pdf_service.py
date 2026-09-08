from weasyprint import HTML


def write_html_as_pdf(html_fragment, output_path):
    document = f"<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head><body>{html_fragment}</body></html>"
    HTML(string=document).write_pdf(output_path)
