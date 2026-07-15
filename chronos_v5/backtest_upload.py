from fpdf import FPDF
import pandas as pd
from datetime import datetime

class PDFBacktestReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Chronos Backtest Report', 0, 1, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 10, body)
        self.ln()

def generate_backtest_pdf(results_df: pd.DataFrame, filename="backtest_report.pdf"):
    pdf = PDFBacktestReport()
    pdf.add_page()
    pdf.chapter_title('Backtest Summary')
    summary = f"Total Trades: {len(results_df)}\n"
    if 'actual_fail' in results_df.columns:
        fail_rate = results_df['actual_fail'].mean()
        summary += f"Failure Rate: {fail_rate:.2%}\n"
    if 'saved' in results_df.columns:
        total_saved = results_df['saved'].sum()
        summary += f"Total Savings: {total_saved:,.2f} NGN\n"
    pdf.chapter_body(summary)
    pdf.output(filename)
    return filename
