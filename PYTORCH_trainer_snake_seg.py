# -*- coding: utf-8 -*-
"""
Created on Sunday Dec. 24th
============================================================
@author: Tiger





TO DO snake seg:
    
    - *** DOUBLE CHECK if need to do CHECK_RESIZE when loading data...
        and if having troubles ==> FIX IN MATLAB

    - add spatial weighting of loss 


"""



""" ALLOWS print out of results on compute canada """
import matplotlib
matplotlib.rc('xtick', labelsize=8)
matplotlib.rc('ytick', labelsize=8) 
#matplotlib.use('Agg')
import matplotlib.pyplot as plt

""" Libraries to load """
import numpy as np
from plot_functions_CLEANED import *
from data_functions_CLEANED import *
from data_functions_3D import *
import glob, os
import datetime
import time
import bcolz
from natsort import natsort_keygen, ns
natsort_key1 = natsort_keygen(key = lambda y: y.lower())      # natural sorting order

import torch
from torch import nn
import torch.nn.functional as F
import torch.optim as optim
from UNet_pytorch import *
from UNet_pytorch_online import *
from PYTORCH_dataloader import *

from sklearn.model_selection import train_test_split

from losses_pytorch.boundary_loss import DC_and_HDBinary_loss, BDLoss, HDDTBinaryLoss
from losses_pytorch.dice_loss import FocalTversky_loss, DC_and_CE_loss
from losses_pytorch.focal_loss import FocalLoss

import kornia

torch.backends.cudnn.benchmark = True  
torch.backends.cudnn.enabled = True 

if __name__ == '__main__':
        
    """ Define GPU to use """
    device = torch.device("cuda:1" if torch.cuda.is_available() else "cpu")
    print(device)
    
    
    """" Input paths """    
    s_path = './(1) Checkpoint_PYTORCH/'
    s_path = './(2) Checkpoint_PYTORCH_spatial_weight/'
    s_path = './(3) Checkpoint_SGD_spatial/'
    s_path = './(4) Checkpoint_AdamW_spatial/'
    #s_path = './(5) Checkpoint_AdamW/'
    #s_path = './(6) Checkpoint_AdamW_FOCALLOSS/'
    #s_path = './(7) Checkpoint_AdamW_spatial_batch_1/'
    #s_path = './(8) Checkpoint_SGD_cyclic_batch_norm/'
    s_path = './(9) Checkpoint_AdamW_batch_norm/'
    #s_path = './(10) Checkpoint_AdamW_batch_norm_SWITCH/'
    #s_path = './(11) Checkpoint_SGD_batch_norm/'
    
    #s_path = './(12) Checkpoint_AdamW_batch_norm_CYCLIC/'
    
    #s_path = './(13) Checkpoint_AdamW_batch_norm_DC_and_HDBinary_loss/'
    
    
    #s_path = './(14) Checkpoint_AdamW_batch_norm_HDBinary_loss/'
    
    #s_path = './(15) Checkpoint_AdamW_batch_norm_SPATIALW/'
    
    
    #s_path = './(16) Checkpoint_AdamW_batch_norm_DICE_CE/'
    
    #s_path = './(17) Checkpoint_AdamW_batch_norm_FOCALLOSS/'
    
    
    #s_path = './(18) Checkpoint_AdamW_batch_norm_SPATIALW_CYCLIC/'
    
    
    #s_path = './(19) Checkpoint_AdamW_batch_norm_HD_and_CE/'
    
    #s_path = './(20) Checkpoint_AdamW_batch_norm_7x7/'
    
    s_path = './(21) Checkpoint_AdamW_batch_norm_3x_branched/'
    
    """ Add Hausdorff + CE??? or + DICE???  + spatial W???"""
    
    
    #input_path = './Train_matched_quads_PYTORCH_256_64_MATCH_ILASTIK/'        
    input_path = '/media/user/storage/Data/(1) snake seg project/Train_SNAKE_SEG_scaled_cleaned/'
    #input_path = '/media/user/storage/Train/'
    #input_path = './Train_SNAKE_SEG_scaled_cleaned/'

    """ TO LOAD OLD CHECKPOINT """
    # Read in file names
    onlyfiles_check = glob.glob(os.path.join(s_path,'check_*'))
    onlyfiles_check.sort(key = natsort_key1)
 
    
        
    # """ load mean and std """  
    mean_arr = np.load('./normalize/' + 'mean_VERIFIED.npy')
    std_arr = np.load('./normalize/' + 'std_VERIFIED.npy')   

    num_workers = 4;
 
    save_every_num_epochs = 1;
    plot_every_num_epochs = 1;
    validate_every_num_epochs = 1;      

    #dist_loss = 0
    dist_loss = 0
    both = 0
    branch_bool = 1
    if both:
        loss_function_2 = torch.nn.CrossEntropyLoss()
        #loss_function = HDDTBinaryLoss(); dist_loss = 1
        
    if not onlyfiles_check:   
        """ Get metrics per batch """
        train_loss_per_batch = []; train_jacc_per_batch = []
        val_loss_per_batch = []; val_jacc_per_batch = []
        """ Get metrics per epoch"""
        train_loss_per_epoch = []; train_jacc_per_epoch = []
        val_loss_per_eval = []; val_jacc_per_eval = []
        plot_sens = []; plot_sens_val = [];
        plot_prec = []; plot_prec_val = [];
        lr_plot = [];
        iterations = 0;
        
        """ Start network """   
        #kernel_size=5
        #pad = int((kernel_size - 1)/2)
        #unet = UNet(in_channel=1,out_channel=2, kernel_size=kernel_size, pad=pad)
        
        kernel_size = 5
        unet = UNet_online(in_channels=2, n_classes=2, depth=5, wf=3, kernel_size = kernel_size, padding= int((kernel_size - 1)/2), 
                           batch_norm=True, batch_norm_switchable=False, up_mode='upconv')
        unet.train()
        unet.to(device)
        print('parameters:', sum(param.numel() for param in unet.parameters()))  
    
        """ Select loss function """
        loss_function = torch.nn.CrossEntropyLoss(reduction='none')
        #kwargs = {"alpha": 0.5, "gamma": 2.0, "reduction": 'none'}
        #loss_function = kornia.losses.FocalLoss(**kwargs)

        
        """ ****** DISTANCE LOSS FUNCTIONS *** CHECK IF NEED TO BE (X,Y,Z) format??? """
        # DC_and_HDBinary_loss, BDLoss, HDDTBinaryLoss
        #loss_function = DC_and_HDBinary_loss(); dist_loss = 1
        #loss_function = HDDTBinaryLoss(); dist_loss = 1
        #if both:
        #    loss_function_2 = torch.nn.CrossEntropyLoss()
            
            
        #loss_function = FocalLoss(apply_nonlin=None, alpha=None, gamma=2, balance_index=0, smooth=1e-5, size_average=True)
        #loss_function = DC_and_CE_loss()

        """ Select optimizer """
        #lr = 1e-3; milestones = [20, 50, 100]  # with AdamW *** EXPLODED ***
        lr = 1e-3; milestones = [5, 50, 100]  # with AdamW
        lr = 1e-5; milestones = [50, 100]  # with AdamW slow down
        lr = 1e-5; milestones = [100]  # with AdamW slow down

        #optimizer = torch.optim.SGD(unet.parameters(), lr = lr, momentum=0.90)
        #optimizer = torch.optim.Adam(unet.parameters(), lr=lr, betas=(0.9, 0.999), eps=1e-08, weight_decay=0, amsgrad=False)
        optimizer = torch.optim.AdamW(unet.parameters(), lr=lr, betas=(0.9, 0.999), eps=1e-08, weight_decay=0.01, amsgrad=False)



        """ Add scheduler """

        # *** IF WITH ADAM CYCLING ==> set cycle_momentum == False
        #scheduler = torch.optim.lr_scheduler.CyclicLR(optimizer, base_lr=1e-7, max_lr=1e-3, step_size_up=2000, step_size_down=None, 
        #                                              mode='triangular', gamma=1.0, scale_fn=None, scale_mode='cycle', 
        #                                              cycle_momentum=False, base_momentum=0.8, max_momentum=0.9, last_epoch=-1)
        
        scheduler = torch.optim.lr_scheduler.MultiStepLR(optimizer, milestones, gamma=0.1, last_epoch=-1)
        resume = 0
        
        """ Prints out all variables in current graph """
        # Required to initialize all
        batch_size = 8;      
        test_size = 0.1
        """ Load training data """
        print('loading data')   
        
        """ Specify transforms """
        #transforms = initialize_transforms(p=0.5)
        #transforms = initialize_transforms_simple(p = 0.5)
        transforms = 0
        
        sp_weight_bool = 0
 
    

    else:             
        """ Find last checkpoint """       
        last_file = onlyfiles_check[-1]
        split = last_file.split('check_')[-1]
        num_check = split.split('.')
        checkpoint = num_check[0]
        checkpoint = 'check_' + checkpoint

        print('restoring weights')
        check = torch.load(s_path + checkpoint)
        cur_epoch = check['cur_epoch']
        iterations = check['iterations']
        idx_train = check['idx_train']
        idx_valid = check['idx_valid']
        
        
        unet = check['model_type']
        optimizer = check['optimizer_type']
        scheduler = check['scheduler_type']
        
        
        unet.load_state_dict(check['model_state_dict'])
        unet.to(device)
        optimizer.load_state_dict(check['optimizer_state_dict'])
        scheduler.load_state_dict(check['scheduler'])
  
        """ Restore per batch """
        train_loss_per_batch = check['train_loss_per_batch']
        train_jacc_per_batch = check['train_jacc_per_batch']
        val_loss_per_batch = check['val_loss_per_batch']
        val_jacc_per_batch = check['val_jacc_per_batch']
     
        """ Restore per epoch """
        train_loss_per_epoch = check['train_loss_per_epoch']
        train_jacc_per_epoch = check['train_jacc_per_epoch']
        val_loss_per_eval = check['val_loss_per_eval']
        val_jacc_per_eval = check['val_jacc_per_eval']
     
        plot_sens = check['plot_sens']
        plot_sens_val = check['plot_sens_val']
        plot_prec = check['plot_prec']
        plot_prec_val = check['plot_prec_val']
     
        lr_plot = check['lr_plot']

        # newly added
        mean_arr = check['mean_arr']
        std_arr = check['std_arr']
        
        batch_size = check['batch_size']
        sp_weight_bool = check['sp_weight_bool']
        loss_function = check['loss_function']
        transforms = check['transforms']

        resume = 1

    """ Load filenames from tiff """
    images = glob.glob(os.path.join(input_path,'*_NOCLAHE_input_crop.tif'))    # can switch this to "*truth.tif" if there is no name for "input"
    images.sort(key=natsort_keygen(alg=ns.REAL))  # natural sorting
    examples = [dict(input=i,truth=i.replace('_NOCLAHE_input_crop.tif','_DILATE_truth_class_1_crop.tif'), seed_crop=i.replace('_NOCLAHE_input_crop','_DILATE_seed_crop')) for i in images]
    counter = list(range(len(examples)))
    
    
    """ Find all indices with _branch so can double them """
    # images_branched = glob.glob(os.path.join(input_path,'*_NOCLAHE_input_crop_BRANCHED.tif'))
    # all_branch_idx = []
    # for filename, idx in zip(images, range(len(images))):
    #     for file_branch, branch_idx in zip(images_branched, range(len(images_branched))):
    #         filename = filename.split('/')[-1]
    #         filename = filename.split('crop.tif')[0]
            
    #         file_branch = file_branch.split('/')[-1]
    #         file_branch = file_branch.split('crop_BRANCHED.tif')[0]
            
    #         if filename == file_branch:
    #             #print('matched')
    #             all_branch_idx.append(idx)
    #             break;

    # np.save(all_branch_idx, './normalize/all_branch_idx.npy')
    
    all_branch_idx = np.load('./normalize/all_branch_idx.npy')
    
    if not resume:
        idx_train, idx_valid, empty, empty = train_test_split(counter, counter, test_size=test_size, random_state=2018)
        
        
        ### DOUBLES anything that is a branch_idx
        if branch_bool:
            match = set(idx_train) & set(all_branch_idx)
            idx_train = idx_train + list(match) + list(match)
            
            # match = set(idx_valid) & set(all_branch_idx)
            # idx_valid = idx_valid + list(match) + list(match)
            
        
        
    training_set = Dataset_tiffs_snake_seg(idx_train, examples, mean_arr, std_arr, sp_weight_bool=sp_weight_bool, transforms = transforms)
    val_set = Dataset_tiffs_snake_seg(idx_valid, examples, mean_arr, std_arr, sp_weight_bool=sp_weight_bool, transforms = 0)
    
    """ Create training and validation generators"""
    val_generator = data.DataLoader(val_set, batch_size=batch_size, shuffle=False, num_workers=num_workers,
                    pin_memory=True, drop_last = True)

    training_generator = data.DataLoader(training_set, batch_size=batch_size, shuffle=True, num_workers=num_workers,
                      pin_memory=True, drop_last=True)
         
    
    
    print('Total # training images per epoch: ' + str(len(training_set)))
    print('Total # validation images: ' + str(len(val_set)))
    

    """ Epoch info """
    train_steps_per_epoch = len(idx_train)/batch_size
    validation_size = len(idx_valid)
    epoch_size = len(idx_train)    




    """ Find LR, to do so must: (1) uncomment section in dataloader """  
    # from torch_lr_finder import LRFinder

    # model = unet
    # loss_function = torch.nn.CrossEntropyLoss()   # *** must use this loss function because dist_loss == mean
    # optimizer = torch.optim.SGD(unet.parameters(), lr = 1e-5, momentum=0.99)
    # #optimizer = torch.optim.AdamW(unet.parameters(), lr=1e-7, betas=(0.9, 0.999), eps=1e-08, weight_decay=0.01, amsgrad=False)
    # lr_finder = LRFinder(model, optimizer, loss_function, device="cuda")
    # lr_finder.range_test(training_generator, val_generator, start_lr=1e-5, end_lr=10, num_iter=50, diverge_th=100000)
    # lr_finder.plot() # to inspect the loss-learning rate graph
    # lr_finder.reset()

    #zzz

    """ Start training """
    for cur_epoch in range(len(train_loss_per_epoch), 10000):  
         unet.train()         
         loss_train = 0
         jacc_train = 0   
                  
         for param_group in optimizer.param_groups:
              #param_group['lr'] = 1e-7   # manually sets learning rate
              cur_lr = param_group['lr']
              lr_plot.append(cur_lr)
              print('Current learning rate is: ' + str(cur_lr))

         iter_cur_epoch = 0;          
         for batch_x, batch_y, spatial_weight in training_generator:
             
                """ Speed testing
                        
                    batch 8, no workers, 50, == 19.74
                    ''' 4 workers ==> 9.2
                
                """
                if iterations == 1:
                    start = time.perf_counter()
                if iterations == 50:
                    stop = time.perf_counter(); diff = stop - start; print(diff)
                    

                """ Plot for debug """ 
                # if iterations % 1 == 0 and iterations != 0:
                #     np_inputs = np.asarray(batch_x.numpy()[0], dtype=np.uint8)
                #     np_labels = np.asarray(batch_y.numpy()[0], dtype=np.uint8)
                #     np_labels[np_labels > 0] = 255
                    
                #     # imsave(s_path + str(iterations) + '_input.tif', np_inputs)
                #     # imsave(s_path + str(iterations) + '_label.tif', np_labels)
                    
                #     in_max = plot_max(np_inputs[0], plot=0)
                #     seed_max = plot_max(np_inputs[1], plot=0)
                #     lb_max = plot_max(np_labels, plot=0)
                    
                #     imsave(s_path + str(iterations) + '_max_input.tif', in_max)
                #     imsave(s_path + str(iterations) + '_max_crop_seed.tif', seed_max)
                #     imsave(s_path + str(iterations) + '_max_label.tif', lb_max)                
                
                """ Load data ==> shape is (batch_size, num_channels, depth, height, width)
                     (1) converts to Tensor
                     (2) normalizes + appl other transforms on GPU
                     (3) ***add non-blocking???
                     ***INPUT LABELS MUST BE < 255??? or else get CudNN error
                     
                """
                inputs, labels = transfer_to_GPU(batch_x, batch_y, device, mean_arr, std_arr)
                inputs = inputs[:, 0, ...]


                """ zero the parameter gradients"""
                optimizer.zero_grad()       
                
                """ forward + backward + optimize """
                output_train = unet(inputs)
                
                
                if dist_loss:  # for distance loss functions
                    labels = labels.unsqueeze(1)
                    labels = labels.permute(0, 1, 3, 4, 2)
                    output_train = output_train.permute(0, 1, 3, 4, 2)
                    
                
                
                loss = loss_function(output_train, labels)
                if both:
                    loss_ce = loss_function_2(output_train.permute(0, 1, 4, 2, 3), labels.permute(0, 1, 4, 2, 3).squeeze())
                    
                    loss = loss + loss_ce
                

                if torch.is_tensor(spatial_weight):
                     spatial_tensor = torch.tensor(spatial_weight, dtype = torch.float, device=device, requires_grad=False)          
                     weighted = loss * spatial_tensor
                     loss = torch.mean(weighted)
                elif dist_loss:
                       loss  # do not do anything if do not need to reduce
                else:
                     loss = torch.mean(loss)   
                     #loss
                
                
                loss.backward()
                optimizer.step()
               
                if dist_loss:  # for distance loss functions
                    labels = labels.permute(0, 1, 4, 2, 3)
                    output_train = output_train.permute(0, 1, 4, 2, 3)
                
                """ Training loss """
                """ ********************* figure out how to do spatial weighting??? """
                train_loss_per_batch.append(loss.cpu().data.numpy());  # Training loss
                loss_train += loss.cpu().data.numpy()
   
                """ Calculate Jaccard on GPU """                 
                jacc = jacc_eval_GPU_torch(output_train, labels)
                jacc = jacc.cpu().data.numpy()
                                            
                jacc_train += jacc # Training jacc
                train_jacc_per_batch.append(jacc)
   
                iterations = iterations + 1       
                iter_cur_epoch += 1
                if iterations % 100 == 0:
                    print('Trained: %d' %(iterations))
                
                
    
         train_loss_per_epoch.append(loss_train/iter_cur_epoch)
         train_jacc_per_epoch.append(jacc_train/iter_cur_epoch)              
    
         """ Should I keep track of loss on every single sample? and iteration? Just not plot it??? """   
         loss_val = 0; jacc_val = 0
         precision_val = 0; sensitivity_val = 0; val_idx = 0;
         iter_cur_epoch = 0; 
         if cur_epoch % validate_every_num_epochs == 0:
             
              with torch.set_grad_enabled(False):  # saves GPU RAM
                   unet.eval()
                   for batch_x_val, batch_y_val, spatial_weight in val_generator:
                        
                        """ Transfer to GPU to normalize ect... """
                        inputs_val, labels_val = transfer_to_GPU(batch_x_val, batch_y_val, device, mean_arr, std_arr)
             
                        inputs_val = inputs_val[:, 0, ...]   
             
                        # forward pass to check validation
                        output_val = unet(inputs_val)

                        if dist_loss:  # for distance loss functions
                            labels_val = labels_val.unsqueeze(1)
                            labels_val = labels_val.permute(0, 1, 3, 4, 2)
                            output_val = output_val.permute(0, 1, 3, 4, 2)                            
                                    
                        loss = loss_function(output_val, labels_val)
                        if both:
                            loss_ce = loss_function_2(output_val.permute(0, 1, 4, 2, 3), labels_val.permute(0, 1, 4, 2, 3).squeeze())
                            
                            loss = loss + loss_ce



                        if torch.is_tensor(spatial_weight):
                               spatial_tensor = torch.tensor(spatial_weight, dtype = torch.float, device=device, requires_grad=False)          
                               weighted = loss * spatial_tensor
                               loss = torch.mean(weighted)
                        elif dist_loss:
                               loss  # do not do anything if do not need to reduce
                            
                        else:
                               loss = torch.mean(loss)  
                               
                               
                        if dist_loss:  # for distance loss functions
                            labels_val = labels_val.permute(0, 1, 4, 2, 3)
                            output_val = output_val.permute(0, 1, 4, 2, 3)
        
                  
                        """ Training loss """
                        val_loss_per_batch.append(loss.cpu().data.numpy());  # Training loss
                        loss_val += loss.cpu().data.numpy()
                                         
                        """ Calculate jaccard on GPU """
                        jacc = jacc_eval_GPU_torch(output_val, labels_val)
                        jacc = jacc.cpu().data.numpy()
                        
                        jacc_val += jacc
                        val_jacc_per_batch.append(jacc)

                        """ Convert back to cpu """                                      
                        output_val = output_val.cpu().data.numpy()            
                        output_val = np.moveaxis(output_val, 1, -1)
                        
                        """ Calculate sensitivity + precision as other metrics ==> only ever on ONE IMAGE of a batch"""
                        batch_y_val = batch_y_val.cpu().data.numpy() 
                        seg_val = np.argmax(output_val[0], axis=-1)  
                        # TP, FN, FP = find_TP_FP_FN_from_im(seg_val, batch_y_val[0])
                                       
                        # if TP + FN == 0: TP;
                        # else: sensitivity = TP/(TP + FN); sensitivity_val += sensitivity;    # PPV
                                       
                        # if TP + FP == 0: TP;
                        # else: precision = TP/(TP + FP);  precision_val += precision    # precision             
              
                        val_idx = val_idx + batch_size
                        print('Validation: ' + str(val_idx) + ' of total: ' + str(validation_size))
                        
                        iter_cur_epoch += 1
                
              
                           
                   val_loss_per_eval.append(loss_val/iter_cur_epoch)
                   val_jacc_per_eval.append(jacc_val/iter_cur_epoch)       
                   
                   #plot_prec.append(precision_val/(validation_size/batch_size))
                   #plot_sens.append(sensitivity_val/(validation_size/batch_size))
                   
                  
                   """ Add to scheduler to do LR decay """
                   scheduler.step()
                  
         if cur_epoch % plot_every_num_epochs == 0:       
              """ Plot sens + precision + jaccard + loss """
              #plot_metric_fun(plot_sens, plot_sens_val, class_name='', metric_name='sensitivity', plot_num=30)
              #plt.figure(30); plt.savefig(s_path + 'Sensitivity.png')
                    
              #plot_metric_fun(plot_prec, plot_prec_val, class_name='', metric_name='precision', plot_num=31)
              #plt.figure(31); plt.savefig(s_path + 'Precision.png')
           
              plot_metric_fun(train_jacc_per_epoch, val_jacc_per_eval, class_name='', metric_name='jaccard', plot_num=32)
              plt.figure(32); plt.savefig(s_path + 'Jaccard.png')
                   
                 
              plot_metric_fun(train_loss_per_epoch, val_loss_per_eval, class_name='', metric_name='loss', plot_num=33)
              plt.figure(33); plt.yscale('log'); plt.savefig(s_path + 'loss_per_epoch.png')          
                   
              
              plot_metric_fun(lr_plot, [], class_name='', metric_name='learning rate', plot_num=35)
              plt.figure(35); plt.savefig(s_path + 'lr_per_epoch.png') 

              """ Plot negative loss """
              if loss < 0:
                  plot_metric_fun(train_loss_per_epoch[cur_epoch - 5: -1], val_loss_per_eval[cur_epoch - 5: -1], class_name='', metric_name='loss', plot_num=36)
                  plt.figure(36); plt.savefig(s_path + 'loss_per_epoch_NEGATIVE.png')     
                  
                  # plot_metric_fun(train_loss_per_batch[iterations - (iter_cur_epoch * 5 * batch_size): -1], val_loss_per_eval[iterations - (iter_cur_epoch * 5): -1], class_name='', metric_name='loss', plot_num=37)
                  # plt.figure(37); plt.savefig(s_path + 'loss_NEGATIVE_ZOOM.png')                   

              """ Plot metrics per batch """                
              plot_metric_fun(train_jacc_per_batch, [], class_name='', metric_name='jaccard', plot_num=34)
              plt.figure(34); plt.savefig(s_path + 'Jaccard_per_batch.png')
                                
              plot_cost_fun(train_loss_per_batch, train_loss_per_batch)                   
              plt.figure(18); plt.savefig(s_path + 'global_loss.png')
              plt.figure(19); plt.savefig(s_path + 'detailed_loss.png')
              plt.figure(25); plt.savefig(s_path + 'global_loss_LOG.png')
              plt.close('all')
                                 
              plot_depth = 8
              output_train = output_train.cpu().data.numpy()            
              output_train = np.moveaxis(output_train, 1, -1)              
              seg_train = np.argmax(output_train[0], axis=-1)  
              
              # convert back to CPU
              batch_x = batch_x.cpu().data.numpy() 
              batch_y = batch_y.cpu().data.numpy() 
              batch_x_val = batch_x_val.cpu().data.numpy()
              
              plot_trainer_3D_PYTORCH_snake_seg(seg_train, seg_val, batch_x[0], batch_x_val[0], batch_y[0], batch_y_val[0],
                                       s_path, iterations, plot_depth=plot_depth)
                                             
              
         """ To save (every x iterations) """
         if cur_epoch % save_every_num_epochs == 0:                          
               save_name = s_path + 'check_' +  str(iterations)               
               torch.save({
                'cur_epoch': cur_epoch,
                'iterations': iterations,
                'idx_train': idx_train,
                'idx_valid': idx_valid,
                
                
                'model_type': unet,
                'optimizer_type': optimizer,
                'scheduler_type': scheduler,
                
                'model_state_dict': unet.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scheduler': scheduler.state_dict(),
                
                'train_loss_per_batch': train_loss_per_batch,
                'train_jacc_per_batch': train_jacc_per_batch,
                'val_loss_per_batch': val_loss_per_batch,
                'val_jacc_per_batch': val_jacc_per_batch,
                
                'train_loss_per_epoch': train_loss_per_epoch,
                'train_jacc_per_epoch': train_jacc_per_epoch,
                'val_loss_per_eval': val_loss_per_eval,
                'val_jacc_per_eval': val_jacc_per_eval,
                
                'plot_sens': plot_sens,
                'plot_sens_val': plot_sens_val,
                'plot_prec': plot_prec,
                'plot_prec_val': plot_prec_val,
                
                'lr_plot': lr_plot,
                
                 # newly added
                'mean_arr': mean_arr,
                'std_arr': std_arr,
                
                'batch_size': batch_size,  
                'sp_weight_bool': sp_weight_bool,
                'loss_function': loss_function,  
                'transforms': transforms  

                
                
                }, save_name)
     
                

                
               
              
              