import os

paths=[
    "other/out2png/svg/result/result_SELECT_2_FermiHubbard2D_cylinder_0_0_2_inner_naive_1_1000000_CareKinkParity",
    "other/out2png/svg/result/result_SELECT_2_FermiHubbard2D_cylinder_0_0_2_inner_random_1_1000000_CareKinkParity",
    "other/out2png/svg/result/result_SELECT_2_FermiHubbard2D_cylinder_0_0_2_inner_SA_1_1000000_CareKinkParity",
    "other/out2png/svg/result/result_SELECT_2_FermiHubbard2D_cylinder_0_0_2_outer_naive_1_1000000_CareKinkParity",
    "other/out2png/svg/result/result_SELECT_2_FermiHubbard2D_cylinder_0_0_2_outer_random_1_1000000_CareKinkParity",
    "other/out2png/svg/result/result_SELECT_2_FermiHubbard2D_cylinder_0_0_2_outer_SA_1_1000000_CareKinkParity",
]

for path in paths:
    from_path=path+"/000.svg"
    to_path="other/out2png/svg/result/{in_out}_{method}.svg".format(in_out=path.split("_")[8], method=path.split("_")[9])
    os.system("cp {from_path} {to_path}".format(from_path=from_path, to_path=to_path))
