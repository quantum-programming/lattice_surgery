import numpy as np
import pandas as pd

pd.options.display.float_format = "{:.3f}".format

path = "../../out/table/select_10_20250121.txt"

with open(path) as f:
    lines = f.readlines()

table = []
for line in lines:
    if line:
        entries = line.split("|")
        table.append(entries)

# print(table)
table_transpose = list(zip(*table))
table_dict = dict()
for column in table_transpose[1:]:
    table_dict[column[0].strip()] = np.array(list(map(int, column[1:])))


single_overhead = (
    table_dict["Single Yes Kink (2.5D SA)"] / table_dict["Single No Kink (2.5D SA)"]
)
double_overhead = (
    table_dict["Double Yes Kink (2D SA)"] / table_dict["Double No Kink (2D SA)"]
)
double_overhead_25d = (
    table_dict["Double Yes Kink (2.5D SA)"] / table_dict["Double No Kink (2.5D SA)"]
)

overhead_df = pd.DataFrame(
    {
        "Single (2.5D)": single_overhead,
        "Double (2D)": double_overhead,
        "Double (2.5D)": double_overhead_25d,
    },
    index=table_transpose[0][1:],
)
print(overhead_df)
print(overhead_df.describe())
