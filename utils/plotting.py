# /utils/plotting.py
import io
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def create_balance_overview_chart(wallets: list, title: str) -> io.BytesIO:
    """Creates a horizontal bar chart of wallet balances."""
    labels = [w.name for w in wallets]
    sizes = [w.balance for w in wallets]
    
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(10, 2 + len(labels) * 0.5))
    
    # Create a color gradient
    vmax = max(abs(s) for s in sizes) if sizes else 1
    if vmax == 0: vmax = 1
    cmap = plt.get_cmap('RdYlGn')
    normalized_values = [(s + vmax) / (2 * vmax) for s in sizes]
    colors = [cmap(nv) for nv in normalized_values]
    
    bars = ax.barh(labels, sizes, color=colors)
    ax.invert_yaxis() # Highest balance on top
    
    ax.set_title(title, fontsize=16)
    ax.set_xlabel("Balance (₹)", fontsize=12)
    ax.set_ylabel("Wallet", fontsize=12)
    ax.grid(axis='x', linestyle='--', alpha=0.6)
    
    # Add labels to bars
    for bar in bars:
        width = bar.get_width()
        label_x_pos = width + (vmax * 0.02) if width >= 0 else width - (vmax * 0.02)
        ha = 'left' if width >= 0 else 'right'
        ax.text(label_x_pos, bar.get_y() + bar.get_height()/2., f'₹{width:,.2f}', va='center', ha=ha)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='PNG')
    plt.close(fig)
    buf.seek(0)
    return buf

def create_period_comparison_chart(p1_data: dict, p2_data: dict, p1_name: str, p2_name: str, title: str) -> io.BytesIO:
    plt.style.use('seaborn-v0_8-whitegrid')
    labels = ['Income', 'Expense']
    period1_metrics = [p1_data.get('income', 0), p1_data.get('expense', 0)]
    period2_metrics = [p2_data.get('income', 0), p2_data.get('expense', 0)]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 7))
    rects1 = ax.bar(x - width/2, period1_metrics, width, label=p1_name, color='#1f77b4')
    rects2 = ax.bar(x + width/2, period2_metrics, width, label=p2_name, color='#ff7f0e')

    ax.set_ylabel('Amount (₹)')
    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.bar_label(rects1, padding=3, fmt='₹{:,.0f}')
    ax.bar_label(rects2, padding=3, fmt='₹{:,.0f}')
    
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='PNG')
    plt.close(fig)
    buf.seek(0)
    return buf

def create_trend_analysis_chart(trend_df: pd.DataFrame, title: str) -> io.BytesIO:
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 7))

    ax.plot(trend_df['Period'], trend_df['Income'], marker='o', linestyle='-', color='g', label='Income')
    ax.plot(trend_df['Period'], trend_df['Expense'], marker='o', linestyle='-', color='r', label='Expense')
    
    ax.set_title(title, fontsize=16)
    ax.set_xlabel("Period", fontsize=12)
    ax.set_ylabel("Amount (₹)", fontsize=12)
    ax.tick_params(axis='x', labelrotation=45)
    ax.legend()
    
    for i, row in trend_df.iterrows():
        if row['Income'] > 0:
            ax.text(i, row['Income'], f" {row['Income']:,.0f}", ha='left', va='bottom', fontsize=9)
        if row['Expense'] > 0:
            ax.text(i, row['Expense'], f" {row['Expense']:,.0f}", ha='left', va='top', fontsize=9)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='PNG')
    plt.close(fig)
    buf.seek(0)
    return buf

def create_expense_pie_chart(expense_df: pd.DataFrame, title: str) -> io.BytesIO:
    chart_data = expense_df.groupby("Category")["Amount"].sum()
    plt.figure(figsize=(8, 6))
    chart_data.plot(kind="pie", autopct="%1.1f%%", ylabel="")
    plt.title(title)
    buf = io.BytesIO()
    plt.savefig(buf, format='PNG')
    plt.close()
    buf.seek(0)
    return buf