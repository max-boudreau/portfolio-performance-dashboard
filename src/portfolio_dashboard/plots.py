import plotly.graph_objects as go
import plotly.express as px

def plot_values(values):
    fig=go.Figure()
    for col in values.columns: fig.add_trace(go.Scatter(x=values.index, y=values[col], mode="lines", name=col))
    fig.update_layout(title="Portfolio Value Over Time", xaxis_title="Date", yaxis_title="Market Value", template="plotly_white", hovermode="x unified")
    return fig

def plot_growth_of_100(portfolio_values, benchmark_prices, blended_returns=None):
    fig=go.Figure(); norm_p=portfolio_values/portfolio_values.iloc[0]*100; norm_b=benchmark_prices/benchmark_prices.iloc[0]*100
    for col in norm_p.columns: fig.add_trace(go.Scatter(x=norm_p.index, y=norm_p[col], mode="lines", name=col))
    for col in norm_b.columns: fig.add_trace(go.Scatter(x=norm_b.index, y=norm_b[col], mode="lines", name=col, line=dict(dash="dash")))
    if blended_returns is not None:
        blended=(1+blended_returns).cumprod()*100
        fig.add_trace(go.Scatter(x=blended.index, y=blended, mode="lines", name="Blended Benchmark", line=dict(dash="dot")))
    fig.update_layout(title="Growth of $100 vs Benchmarks", xaxis_title="Date", yaxis_title="Growth of $100", template="plotly_white", hovermode="x unified")
    return fig

def plot_drawdown(returns):
    fig=go.Figure()
    for col in returns.columns:
        cumulative=(1+returns[col].dropna()).cumprod(); dd=cumulative/cumulative.cummax()-1
        fig.add_trace(go.Scatter(x=dd.index, y=dd, mode="lines", name=col))
    fig.update_layout(title="Drawdown Analysis", xaxis_title="Date", yaxis_title="Drawdown", template="plotly_white", hovermode="x unified")
    return fig

def plot_allocation(allocation_df, portfolio):
    df=allocation_df[allocation_df["Portfolio"]==portfolio]
    fig=px.pie(df, names="Ticker", values="Market Value", title=f"{portfolio} Current Allocation")
    fig.update_traces(textposition="inside", textinfo="percent+label"); return fig

def plot_sector_allocation(sector_df, portfolio):
    df=sector_df[sector_df["Portfolio"]==portfolio]
    return px.bar(df, x="Sector", y="Weight", title=f"{portfolio} Sector Allocation", text_auto=".1%")

def plot_monthly_heatmap(portfolio_returns, title):
    m=portfolio_returns.resample("ME").apply(lambda x:(1+x).prod()-1); df=m.to_frame("Return"); df["Year"]=df.index.year; df["Month"]=df.index.strftime("%b")
    order=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    table=df.pivot(index="Year", columns="Month", values="Return").reindex(columns=order)
    return px.imshow(table, text_auto=".1%", title=title, color_continuous_scale="RdYlGn", aspect="auto")
