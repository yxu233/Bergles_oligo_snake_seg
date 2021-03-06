# -*- coding: utf-8 -*-
"""
Created on Sunday Dec. 24th
============================================================
@author: Tiger




### TO DO:
    # (1) setup full auto
    # (2) setup validation
    # (3) test different models

    # (4) paranodes
    # (5) plot single sample validation loss ==> DONE
    
    
    # (6) setup MARCC training
    # (7) msg Cody
    
    
    ***upgrade pytorch:
              conda update pytorch torchvision -c pytorch
              
    *** to downgrade pytorch:
              conda install pytorch=0.1.10 -c soumith          
    


"""
import matplotlib
matplotlib.rc('xtick', labelsize=8) 
matplotlib.rc('ytick', labelsize=8) 
#matplotlib.use('Qt5Agg')


""" Libraries to load """
import numpy as np
from functional.plot_functions_CLEANED import *
from functional.data_functions_CLEANED import *
from functional.data_functions_3D import *
from functional.IO_func import *
import glob, os
import datetime
import time
from natsort import natsort_keygen, ns
natsort_key1 = natsort_keygen(key = lambda y: y.lower())      # natural sorting order

import torch
from torch import nn
import torch.nn.functional as F
import torch.optim as optim
from layers.UNet_pytorch import *
from layers.UNet_pytorch_online import *
from sklearn.model_selection import train_test_split

from matlab_crop_function import *
from off_shoot_functions import *
from tree_functions import *
from skimage.morphology import skeletonize_3d, skeletonize
from skimage.transform import rescale, resize, downscale_local_mean

from PYTORCH_dataloader import *
torch.backends.cudnn.benchmark = True  
torch.backends.cudnn.enabled = True 

import re

""" Define GPU to use """
import torch
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(device)


"""  Network Begins: """

z_size = 48
check_path = '/media/user/storage/Data/(1) snake seg project/Backup checkpoints/(65) Checkpoint_unet_LARGE_filt7x7_b4_NEW_DATA_B_NORM_crop_pad_Hd_loss_balance_NO_1st_im_2_step_REAL_HISTORICAL/';  dilation = 1; deep_supervision = False; tracker = 1; HISTORICAL = 1;

s_path = '/media/user/storage/Data/(1) snake seg project/Traces files/rerun training data seed 2/'; dataset = 'historical seed 2 z 48'
    
try:
    # Create target Directory
    os.mkdir(s_path)
    print("Directory " , s_path ,  " Created ") 
except FileExistsError:
    print("Directory " , s_path ,  " already exists")

input_path = '/media/user/storage/Data/(1) snake seg project/Traces files/TRAINING FORWARD PROP ONLY SCALED crop pads seed 2 COLORED 48 z/TRAINING FORWARD PROP seed 2 COLORED 48 z DATA/'; dataset = 'historical seed 2 z 48'
   
""" Also load in the all_tree_indices file """
tree_csv_path = '/media/user/storage/Data/(1) snake seg project/Traces files/TRAINING FORWARD PROP ONLY SCALED crop pads seed 2 COLORED 48 z/'
all_trees = load_all_trees(tree_csv_path)
    

""" TO LOAD OLD CHECKPOINT """
onlyfiles_check = glob.glob(os.path.join(check_path,'check_*'))
onlyfiles_check.sort(key = natsort_key1)
    
""" Find last checkpoint """       
last_file = onlyfiles_check[-1]
split = last_file.split('check_')[-1]
num_check = split.split('.')
checkpoint = num_check[0]
checkpoint = 'check_' + checkpoint

print('restoring weights of checkpoint: ' + str(num_check[0]))
check = torch.load(check_path + checkpoint, map_location=device)
unet = check['model_type']
unet.load_state_dict(check['model_state_dict']) 


if not tracker:
    mean_arr = check['mean_arr'];  std_arr = check['std_arr']
else:
    ### IF LOAD WITH TRACKER
    tracker = check['tracker']
    mean_arr = tracker.mean_arr; std_arr = tracker.std_arr


""" Set to eval mode for batch norm """
unet.eval()
#unet.training # check if mode set correctly
unet.to(device)

input_size = 80
depth = 48

crop_size = int(input_size/2)
z_size = depth


""" Load filenames from tiff """
images = glob.glob(os.path.join(input_path,'*_NOCLAHE_input_crop.tif'))    # can switch this to "*truth.tif" if there is no name for "input"
images.sort(key=natsort_keygen(alg=ns.REAL))  # natural sorting
examples = [dict(input=i,truth=i.replace('_NOCLAHE_input_crop.tif','_DILATE_truth_class_1_crop.tif'), 
                 seed_crop=i.replace('_NOCLAHE_input_crop','_DILATE_seed_crop'),  
                 orig_idx= int(re.search('_origId_(.*)_eId', i).group(1)),
                 filename= i.split('/')[-1].split('_origId')[0].replace(',', ''))
                 for i in images]
counter = list(range(len(examples)))

""" Create datasets for dataloader """
training_set = Dataset_tiffs_snake_seg(counter, examples, mean_arr, std_arr, sp_weight_bool=0, transforms = 0, all_trees=all_trees)

training_generator = data.DataLoader(training_set, batch_size=1, shuffle=False, num_workers=0,
                  pin_memory=True, drop_last=True)


print('Total # training images per epoch: ' + str(len(training_set)))

for cur_epoch in range(10000): 
     
     unet.eval()         

    
     iter_cur_epoch = 0;   
     starter = 0;
     for batch_x, batch_y, spatial_weight in training_generator:    
         
                inputs, labels = transfer_to_GPU(batch_x, batch_y, device, mean_arr, std_arr)
                inputs = inputs[:, 0, ...]

                """ forward + backward + optimize """
                output_train = unet(inputs)  
                
                """ Plot for ground truth """
                output_train = output_train.cpu().data.numpy()            
                output_train = np.moveaxis(output_train, 1, -1)              
                seg_train = np.argmax(output_train[0], axis=-1)  
                  
                # convert back to CPU
                batch_x = batch_x.cpu().data.numpy() 
                batch_y = batch_y.cpu().data.numpy() 
 
                plot_trainer_3D_PYTORCH_snake_seg(seg_train, seg_train, batch_x[0], batch_x[0], batch_y[0], batch_y[0],
                                            s_path, iter_cur_epoch, plot_depth=8)
                
                
                
                plt.figure(100);
                im_idx = 1
                for p_idx in range(2, len(batch_x[0]), 2):
                    
                    im = batch_x[0][p_idx]
                
                    plt.subplot(2, 10, im_idx)
                    ma = plot_max(im, plot=0)
                    plt.imshow(ma); plt.axis('off')
                    
                    im = batch_x[0][p_idx + 1]
                    plt.subplot(2, 10, (im_idx + 10))
                    ma = plot_max(im, plot=0)
                    plt.imshow(ma); plt.axis('off')
                    
                    im_idx += 1
          
                    print(p_idx)
            
                    
                plt.savefig(s_path + '_'   + str(iter_cur_epoch) + '_HISTORICAL.png')
                plt.close('all')
                                
                iter_cur_epoch += 1
      
      
                
                
                
                
                
                
                
                
                
                
                
                