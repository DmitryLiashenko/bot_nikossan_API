import torch

state_dict = torch.load("sam_vit_h_4b8939.pth")
print(state_dict.keys())
