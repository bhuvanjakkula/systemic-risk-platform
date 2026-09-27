SAMPLE = {
    'entities': [
        {'id': 'Bank-A', 'assets': 100, 'capital': 10, 'liquidity': 20},
        {'id': 'Bank-B', 'assets': 100, 'capital': 8, 'liquidity': 10},
        {'id': 'Bank-C', 'assets': 100, 'capital': 6, 'liquidity': 5},
    ],
    'exposures': [
        {'creditor': 'Bank-B', 'debtor': 'Bank-A', 'amount': 20},
        {'creditor': 'Bank-C', 'debtor': 'Bank-B', 'amount': 15},
    ],
    'shocks': {'Bank-A': 0.12},
}
