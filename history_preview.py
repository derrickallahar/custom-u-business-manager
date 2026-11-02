"""Fixed synthetic history fixtures. No real exports are included or loaded."""
RECORDS = [
 {'kind':'invoice','number':'TEST-H-1001','customer':'TEST Archive Customer','status':'past_due','total':'110.00','balance':'60.00','details':'Historical summary only; item details unavailable. Payment allocations unknown.'},
 {'kind':'quote','number':'TEST-Q-1001','customer':'TEST Archive Customer','status':'draft','total':'220.00','balance':'220.00','details':'Historical summary only; item details unavailable.'},
 {'kind':'payment','number':'TEST-P-1001','customer':'TEST Archive Customer','status':'Completed','total':'50.00','balance':'','details':'Unallocated historical reference. Not posted to live invoices.'},
]
