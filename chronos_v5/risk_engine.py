# chronos_v5/risk_engine.py — key excerpt
def compute_all(self, tenant: str, desk=None):
    """
    tenant is now a required parameter. It previously defaulted to None,
    and on a None/falsy tenant the query below skipped the
    Trade.tenant == tenant filter entirely — silently computing VaR/ES/
    stress loss across every tenant's trades merged together, then
    persisting that blended figure mislabeled as tenant "default" (see
    `tenant=tenant or "default"` that used to sit on the RiskMetrics
    write below). For a bank consuming this number as their own VaR,
    that's a materially wrong risk figure, not just a lookup bug — same
    root cause as the tenant-write bug fixed in trade_repository.insert().
    Callers that genuinely want a platform-wide view (e.g. an internal
    ops task) must loop over real tenants explicitly and call this once
    per tenant — see tasks.compute_risk_metrics for the corrected
    pattern — rather than relying on an implicit "no filter" mode here.
    """
    if not tenant:
        raise ValueError("tenant is required for compute_all() — refusing to "
                          "compute risk metrics across an unscoped, merged set "
                          "of trades from every tenant.")
    db = SyncSessionLocal()
    try:
        query = db.query(Trade).filter(
            Trade.created_at > datetime.now() - timedelta(days=30),
            Trade.tenant == tenant,
        )
        if desk:
            query = query.filter(Trade.desk == desk)
        trades = query.all()
        if not trades:
            logger.info("No trades for risk computation")
            return None

        instrument_types = list(set(t.instrument_type for t in trades if t.instrument_type))
        if not instrument_types:
            logger.warning("No instrument types found, cannot compute risk")
            return None

        cutoff = datetime.now() - timedelta(days=31)
        market_data = db.query(MarketDataPoint).filter(
            MarketDataPoint.symbol.in_(instrument_types),
            MarketDataPoint.timestamp >= cutoff
        ).order_by(MarketDataPoint.timestamp).all()

        price_series = defaultdict(list)
        for dp in market_data:
            price_series[dp.symbol].append((dp.timestamp, dp.price))

        pnl_changes = []
        estimated_count = 0
        total_notional = 0.0

        for t in trades:
            if not t.instrument_type or t.instrument_type not in price_series:
                estimated_count += 1
                continue
            series = price_series[t.instrument_type]
            trade_time = t.created_at
            before = None
            after = None
            for ts, price in series:
                if ts <= trade_time:
                    before = (ts, price)
                else:
                    after = (ts, price)
                    break
            if before and after:
                change = (after[1] - before[1]) / before[1] if before[1] != 0 else 0
                pnl_changes.append(t.notional * change)
                total_notional += t.notional
            else:
                estimated_count += 1

        if not pnl_changes:
            logger.warning("No trades with market data; risk metrics cannot be computed.")
            return {
                "desk": desk or "TOTAL",
                "tenant": tenant,
                "var_99": None,
                "expected_shortfall": None,
                "stress_loss": None,
                "capital_usage": None,
                "data_quality": {
                    "total_trades": len(trades),
                    "estimated_trades": estimated_count,
                    "message": "No trades had market data; VaR not computed"
                }
            }

        returns = np.array(pnl_changes) / total_notional if total_notional > 0 else np.array(pnl_changes)
        var = self.compute_var(returns, Config.VAR_CONFIDENCE)
        es = self.compute_expected_shortfall(returns, Config.VAR_CONFIDENCE)
        stress = self.compute_stress_loss(returns, "NIGERIA_2020")

        metric = RiskMetrics(
            desk=desk or "TOTAL",
            tenant=tenant,
            var_99=var,
            expected_shortfall=es,
            stress_loss=stress,
            capital_usage=abs(var) * Config.CAPITAL_REQUIREMENT_SA_CCR
        )
        db.add(metric)
        db.commit()
        logger.info(f"Risk metrics computed for {desk or 'TOTAL'} (excluded {estimated_count} trades with no market data)")

        result = {
            "desk": metric.desk,
            "tenant": metric.tenant,
            "var_99": metric.var_99,
            "expected_shortfall": metric.expected_shortfall,
            "stress_loss": metric.stress_loss,
            "capital_usage": metric.capital_usage,
            "timestamp": metric.timestamp,
            "data_quality": {
                "total_trades": len(trades),
                "estimated_trades": estimated_count,
                "message": f"Excluded {estimated_count} trades with no market data"
            }
        }
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
