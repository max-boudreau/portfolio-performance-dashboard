def build_blended_benchmark(benchmark_prices, weights):
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6: weights = {k: v / total for k, v in weights.items()}
    returns = benchmark_prices.pct_change().dropna()
    missing = [t for t in weights if t not in returns.columns]
    if missing: raise ValueError(f"Missing benchmark price data for: {missing}")
    return sum(returns[ticker] * weight for ticker, weight in weights.items())
