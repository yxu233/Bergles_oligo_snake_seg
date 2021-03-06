# -*- coding: utf-8 -*-
"""
Created on Sun May 10 21:10:03 2020

@author: tiger
"""


import torchvision.transforms.functional as TF
import random
from torch.utils import data
import torch
import time
import numpy as np

import scipy
import math
import tifffile as tifffile

import skimage

import matplotlib.pyplot as plt

import matlab_crop_function



def plot_max(im, ax=0, plot=1):
     max_im = np.amax(im, axis=ax)
     if plot:
         plt.figure(); plt.imshow(max_im)
     
     return max_im
 
""" dilates image by a spherical ball of size radius """
def dilate_by_ball_to_binary(input_im, radius):
     ball_obj = skimage.morphology.ball(radius=radius)
     input_im = skimage.morphology.dilation(input_im, selem=ball_obj)  
     input_im[input_im > 0] = 1
     return input_im
 
    
 
    

""" Define transforms"""
import torchio
from torchio.transforms import (
    RescaleIntensity,
    RandomFlip,
    RandomAffine,
    RandomElasticDeformation,
    RandomMotion,
    RandomBiasField,
    RandomBlur,
    RandomAnisotropy,
    RandomNoise,
    #Interpolation,
    Compose
)
#from torchio import Image, Subject, ImagesDataset


import torchio as tio


def initialize_transforms_simple(p=0.8):
     transforms = [
           RandomFlip(axes = (0, 1, 2), flip_probability = 1, p = p),
           
           #RandomAffine(scales=(0.9, 1.1), degrees=(10), isotropic=False,
           #             default_pad_value='otsu', image_interpolation=Interpolation.LINEAR,
           #             p = p, seed=None),
           
           # *** SLOWS DOWN DATALOADER ***
           #RandomElasticDeformation(num_control_points = 7, max_displacement = 7.5,
           #                         locked_borders = 2, image_interpolation = Interpolation.LINEAR,
           #                         p = 0.5, seed = None),
           RandomMotion(degrees = 10, translation = 10, num_transforms = 2, image_interpolation = 'linear',
                        p = p),
           
           RandomAnisotropy(axes=(0, 1, 2), downsampling=2),
           
           RandomBiasField(coefficients=0.5, order = 3, p = p),
           
           RandomBlur(std = (0, 2), p = p),
           
           RandomNoise(mean = 0, std = (0, 5), p = p),
           RescaleIntensity((0, 255))
           
     ]
     transform = tio.Compose(transforms)
     return transform


from functional.data_functions_CLEANED import *
from functional.data_functions_3D import *
from skimage.morphology import skeletonize_3d, skeletonize
from functional.plot_functions_CLEANED import *
from skan import skeleton_to_csgraph
from skimage.draw import line_nd

from skimage.transform import resize

from tree_functions import *




""" Calculate Jaccard on the GPU """
def jacc_eval_GPU_torch(output, truth, ax_labels=-1, argmax_truth=1):
    
      output = torch.argmax(output,axis=1)
      intersection = torch.sum(torch.sum(output * truth, axis=ax_labels),axis=ax_labels)
      union = torch.sum(torch.sum(torch.add(output, truth)>= 1, axis=ax_labels),axis=ax_labels) + 0.0000001
      jaccard = torch.mean(intersection / union)  # find mean of jaccard over all slices     
          
      
      ### per image ==> is the same???
      # all_jacc = [];
      # for o_single, t_single in zip(output, truth):
      #     o_single = torch.argmax(o_single,axis=0)
      #     intersection = torch.sum(torch.sum(o_single * t_single, axis=ax_labels),axis=ax_labels)
      #     union = torch.sum(torch.sum(torch.add(o_single, t_single)>= 1, axis=ax_labels),axis=ax_labels) + 0.0000001
      #     jaccard = torch.mean(intersection / union)  # find mean of jaccard over all slices   
      #     all_jacc.append(jaccard.cpu().data.numpy())

          
      return jaccard


""" Find cID metric: """
import cIDice_metric as cID_metric
def cID_metric_eval_CPU(output_train, labels):
    ### FOR DEBUGGING:

    labels = labels.cpu().data.numpy()                  
    output_train = output_train.cpu().data.numpy()            
    output_train = np.moveaxis(output_train, 1, -1)   
    
    sum_cID = 0
    for i in range(len(output_train)):
    
        seg_val = np.argmax(output_train[i], axis=-1)  
        truth_3D = labels[i]
        cID_val_3D = cID_metric.clDice(truth_3D, seg_val)
        
        sum_cID += cID_val_3D
        
    return sum_cID/len(output_train)
                           







""" Extended functions for SNAKE_SEG """
def get_parents_csv_tree(tree, cur_val, parents, num_parents=10):
    if cur_val == 0 or num_parents == 0:
        return parents
    
    else:
        loc_idx = np.where(tree['orig_idx'] == cur_val)
        
        parent = tree['parents'][loc_idx][0]
        #print(parent)
    
        parents.append(parent)
    
        parents = get_parents_csv_tree(tree, cur_val=parent, parents=parents, num_parents=num_parents - 1)

        return parents

    
def get_examples_arr(examples):
    examples_arr = {}
    for k in list(examples[0].keys()):
        examples_arr[k] = tuple(examples_arr[k] for examples_arr in examples)
           
    return examples_arr

               
                
""" Load data directly from tiffs with seed mask """
class Dataset_tiffs_snake_seg(data.Dataset):
  def __init__(self, list_IDs, examples, mean, std, sp_weight_bool=0, transforms=0, dist_loss=0, resize_z=0, skeletonize=0, depth=48, num_parents = 10, all_trees=[], HISTORICAL=0):
        'Initialization'
        #self.labels = labels
        self.list_IDs = list_IDs
        self.examples = np.copy(examples)
        self.transforms = transforms
        self.mean = mean
        self.std = std
        self.sp_weight_bool = sp_weight_bool
        self.dist_loss = dist_loss
        self.resize_z = resize_z
        
        self.cube = create_cube_in_im(width=8, input_size=80, z_size=80)
        
        self.skeletonize = skeletonize
        self.all_trees = all_trees
        
        self.num_parents = num_parents
        
        
        ### Define orig idx and start indices so can be found easier later
        self.examples_arr = get_examples_arr(examples)
        #self.all_orig_idx = np.asarray(self.examples_arr['orig_idx'])
        #self.all_start_indices =  np.where(self.all_orig_idx == 1)[0]
        
        self.height = 80; self.width = 80; self.depth = depth;
        
        self.HISTORICAL = HISTORICAL
        

  def apply_transforms(self, image, labels):
        #inputs = np.asarray(image, dtype=np.float32)
        inputs = image

 
        inputs = torch.tensor(inputs, dtype = torch.float,requires_grad=False)
        labels = torch.tensor(labels, dtype = torch.long, requires_grad=False)      
        
        
        """ Expected input is:   (C x W x H x D) """
        inputs = inputs.unsqueeze(0)
        inputs = torch.moveaxis(inputs, 1, -1)
        
        labels = labels.unsqueeze(0)
        labels = torch.moveaxis(labels, 1, -1)
        
 
        subject_a = tio.Subject(
                one_image=tio.ScalarImage(tensor=inputs),   # *** must be tensors!!!
                a_segmentation=tio.LabelMap(tensor=labels))
          
        subjects_list = [subject_a]

        subjects_dataset = tio.SubjectsDataset(subjects_list, transform=self.transforms)
        subject_sample = subjects_dataset[0]
          
          
        X = subject_sample['one_image']['data'].numpy()
        Y = subject_sample['a_segmentation']['data'].numpy()
        
        
        """ Re-arrange channels for Pytorch into (D, H, W) """
        X = X[0]
        X = np.moveaxis(X, -1, 0)
        
        Y = Y[0]
        Y = np.moveaxis(Y, -1, 0)


        """ DEBUG """
        #plot_max(X)
        #plot_max(Y)
  
    
  
        return X, Y

    
  def append_seed_mask(self, image, seed_crop):
     
        #seed_crop[seed_crop > 0] = 1

        """ Added because need to check to make sure no objects leaving out of frame during small crop 
        
                *** DOUBLE CHECK THIS IN MATLAB???
        
        """
        #seed_crop = np.expand_dims(seed_crop, axis=0)
        #seed_crop = check_resized(seed_crop, depth, width_max=input_size, height_max=input_size)
        #seed_crop = seed_crop[:, :, :, 0]

    
        """ Append seed to input """
        temp = np.zeros((2, ) + np.shape(image))
        temp[0,...] = image
        seed_crop[seed_crop > 0] = 255
        temp[1,...] = seed_crop
                             
        return temp
    
  # def create_dist_loss(self, labels):
  #        posmask = labels
  #        negmask = ~posmask
  #        spatial_weight = scipy.ndimage.distance_transform_cdt(posmask) + scipy.ndimage.distance_transform_cdt(negmask)

  #        return spatial_weight
     
        
     
  def create_spatial_weight_mat(self, labels, edgeFalloff=10,background=0.01,approximate=True):
       
         if approximate:   # does chebyshev
             dist1 = scipy.ndimage.distance_transform_cdt(labels)
             dist2 = scipy.ndimage.distance_transform_cdt(np.where(labels>0,0,1))    # sets everything in the middle of the OBJECT to be 0
                     
         else:   # does euclidean
             dist1 = scipy.ndimage.distance_transform_edt(labels, sampling=[1,1,1])
             dist2 = scipy.ndimage.distance_transform_edt(np.where(labels>0,0,1), sampling=[1,1,1])
             
         """ DO CLASS WEIGHTING instead of spatial weighting WITHIN the object """
         dist1[dist1 > 0] = 0.5
     
         dist = dist1+dist2
         attention = math.e**(1-dist/edgeFalloff) + background   # adds background so no loses go to zero
         attention /= np.average(attention)
         return np.reshape(attention,labels.shape)    
     
        
  def skel(self, seed, truth):
        """ resize_z dimension of all inputs """
        
        ### (2) resize seed
        #seed = batch_x[0][1].cpu().data.numpy()    
        skel = skeletonize_3d(seed)

        """ Link to center """
        center = [15, 39, 30]
        degrees, coordinates = bw_skel_and_analyze(skel)
        coord_end = np.transpose(np.vstack(np.where(degrees == 1)))
        
        for coord in coord_end:
            
            #print(np.linalg.norm(center - coord))
            if np.linalg.norm(center - coord) <= 10:
                line_coords = line_nd(center, coord, endpoint=False)
                line_coords = np.transpose(line_coords)      
                
                skel[line_coords[:, 0], line_coords[:, 1], line_coords[:, 2]] = 1
                skel[center[0], center[1], center[2]] = 1

        seed_skel = skel
        seed_skel[seed_skel > 0] = 255
        


        
        ### (3) resize truth
        #truth = np.asarray(batch_y[0].cpu().data.numpy(), dtype=np.float64)
        #truth[truth > 0] = 255
        skel = skeletonize_3d(truth)
        
        """ Link to center """
        center = [15, 39, 39]
        degrees, coordinates = bw_skel_and_analyze(skel)
        coord_end = np.transpose(np.vstack(np.where(degrees == 1)))
        
        for coord in coord_end:
            #print(np.linalg.norm(center - coord))
            if np.linalg.norm(center - coord) <= 10:
                line_coords = line_nd(center, coord, endpoint=False)
                line_coords = np.transpose(line_coords)      
                
                skel[line_coords[:, 0], line_coords[:, 1], line_coords[:, 2]] = 1
                
                skel[center[0], center[1], center[2]] = 1

        """ Dilate to ball """
        truth_skel = skel
        
        return seed_skel, truth_skel


  """ Skeletonize image """

  def resize_z_func(self, raw, seed, truth):
        """ resize_z dimension of all inputs """
        
        ### (1) resize raw
        #raw = batch_x[0][0].cpu().data.numpy()        
        raw_resize = resize(np.asarray(raw, dtype=np.float32), [80, 80, 80], order = 1)
        
        ### (2) resize seed
        #seed = batch_x[0][1].cpu().data.numpy()    
        seed = skeletonize_3d(seed)
        seed_resize = resize(np.asarray(seed, dtype=np.float32), [80, 80, 80], order = 1)
        #seed_resize[seed_resize > 0] = 255
        seed_resize[seed_resize <= 100] = 0; seed_resize[seed_resize >= 100] = 1;
        skel = skeletonize_3d(seed_resize)
        
        ### subtract out cube in middle
        skel[self.cube == 1] = 0


        """ Link to center """
        center = [39, 39, 39]
        degrees, coordinates = bw_skel_and_analyze(skel)
        coord_end = np.transpose(np.vstack(np.where(degrees == 1)))
        
        for coord in coord_end:
            
            #print(np.linalg.norm(center - coord))
            if np.linalg.norm(center - coord) <= 10:
                line_coords = line_nd(center, coord, endpoint=False)
                line_coords = np.transpose(line_coords)      
                
                skel[line_coords[:, 0], line_coords[:, 1], line_coords[:, 2]] = 1
                skel[center[0], center[1], center[2]] = 1
                
        seed_resize = dilate_by_ball_to_binary(skel, radius = 1)
        seed_resize[seed_resize > 0] = 255
        


        
        ### (3) resize truth
        #truth = np.asarray(batch_y[0].cpu().data.numpy(), dtype=np.float64)
        truth[truth > 0] = 255
        truth = skeletonize_3d(truth)
        truth_resize = resize(np.asarray(truth, dtype=np.float32), [80, 80, 80], order = 1)
        truth_resize[truth_resize <= 100] = 0; truth_resize[truth_resize >= 100] = 1;
        
        skel = skeletonize_3d(truth_resize)
        
        
        ### subtract out cube in middle
        skel[self.cube == 1] = 0
        
        """ Link to center """
        center = [39, 39, 39]
        degrees, coordinates = bw_skel_and_analyze(skel)
        coord_end = np.transpose(np.vstack(np.where(degrees == 1)))
        
        for coord in coord_end:
            #print(np.linalg.norm(center - coord))
            if np.linalg.norm(center - coord) <= 10:
                line_coords = line_nd(center, coord, endpoint=False)
                line_coords = np.transpose(line_coords)      
                
                skel[line_coords[:, 0], line_coords[:, 1], line_coords[:, 2]] = 1
                
                skel[center[0], center[1], center[2]] = 1

        """ Dilate to ball """
        truth_resize = dilate_by_ball_to_binary(skel, radius = 1)


        """ If want to load parents as well """
  def load_HISTORICAL_internodes(self, index, num_parents, seed_orig, Y_orig):
        ### Find matching tree from all_trees that matches with example
        im_name = self.examples[index]['filename']
        cur_val = self.examples[index]['orig_idx']
        
                
        """ If parents were found: """
        all_parent_im = []
        parents = []
      
        """ add current value to list of parents so can include past traces of itself as well 
                ***maybe move this to before this if statement???
        """
        parents = [cur_val] + parents
        
        ### then search through examples to find matching
        
        ### to save memory, only search through - 10000 examples           
            
        index_beginning_of_im = np.max(np.where(self.all_start_indices <= index)[0])
        start_im_num = self.all_start_indices[index_beginning_of_im]
        while len(np.where(self.all_start_indices == start_im_num)[0]) > 0:
            start_im_num -= 1
        start_im_num += 1
            
        search_examples = self.examples[start_im_num:index]
        
        search_example_orig_idx = self.all_orig_idx[start_im_num:index]
        
        
        """ Grab random image from within the parent seed 
        
                OR actually, get parents exactly 20 pixels apart from each other (i.e. every 4 +/- 1 crops from each other)
        """
        from random import randint
        all_parent_indices = []
        for parent in parents:
            
            if parent != 0:
                loc_parent = np.where(search_example_orig_idx == parent)[0]
                #rand_idx = randint(0, len(loc_parent) - 1)
                #parent_idx = loc_parent[rand_idx] + start_im_num
                #all_parent_indices.append(parent_idx)
                
                all_parent_indices = np.concatenate((all_parent_indices, loc_parent))
            
        all_parent_indices = np.unique(all_parent_indices) ### REMOVE DUPLICATES
        all_parent_indices[::-1].sort()  ### sort into descending order
        
        get_every = 4   ### because 8 pixels apart * 4 == 32
        all_parent_indices_skip = []
        for idx, val in enumerate(all_parent_indices):
            rand_idx = randint(-2, 0)
            
            if idx % get_every == 0:           
                if idx == 0:
                    skip = 1;
                    """ Tiger added ==> skip very first trace!!! otherwise crop seed will be IN THE FOV!!! """
                    # if  idx + 2 < len(all_parent_indices):
                    #     # don't get crop immediately a
                    #     idx = 2
                    # else:                
                    #     all_parent_indices_skip.append(int(all_parent_indices[idx]))
                        
                else:
                    all_parent_indices_skip.append(int(all_parent_indices[idx + rand_idx]))
                
                
            
        #all_parent_indices_skip = all_parent_indices[0::4]  ### get every 4th index
        
        
        """ Get real current crop size!!! so can compare """
        ID = self.list_IDs[index]

        input_orig = self.examples[ID]['input']
        # truth_name = self.examples[ID]['truth']
        # seed_name = self.examples[ID]['seed_crop']

        X_orig = tifffile.imread(input_orig)
        
        # Y_orig = tifffile.imread(truth_name)
        # seed_orig = tifffile.imread(seed_name)
        # Y[Y > 0] = 1
        # plot_max(Y_orig); plot_max(seed_orig); plot_max(X_orig); plot_max(X); plot_max(Y); plot_max(seed_crop)
        x_scale = self.examples[ID]['x']
        y_scale = self.examples[ID]['y']
        z_scale = self.examples[ID]['z']
        coords_Y_orig = np.transpose(np.where(Y_orig > 0))
        # coords_Y_orig[:, 0] = coords_Y_orig[:, 0] - np.shape(X_orig)[0]/2
        # coords_Y_orig[:, 1] = coords_Y_orig[:, 1] - np.shape(X_orig)[1]/2
        # coords_Y_orig[:, 2] = coords_Y_orig[:, 2] - np.shape(X_orig)[2]/2
        
        coords_Y_orig[:, 0] = coords_Y_orig[:, 0] + z_scale
        coords_Y_orig[:, 1] = coords_Y_orig[:, 1] + x_scale
        coords_Y_orig[:, 2] = coords_Y_orig[:, 2] + y_scale  
        
        coords_Y_orig = expand_coord_to_neighborhood(coords_Y_orig, 3, 4)
        coords_Y_orig = np.unique(coords_Y_orig,axis=0)
                        
        
        """ Scale indices to size of whole list """
        all_parent_indices_skip = all_parent_indices_skip + start_im_num
     
        """ Actually load the parents """         
        for parent_idx in all_parent_indices_skip:
     
            input_name = self.examples[parent_idx]['input']    ### SCALE NUMBER BACK
            truth_name = self.examples[parent_idx]['truth']
            seed_name = self.examples[parent_idx]['seed_crop']

            X = tifffile.imread(input_name)
            Y = tifffile.imread(truth_name)
            seed_crop = tifffile.imread(seed_name)
            
            """ Get location """
            x_scale = self.examples[parent_idx]['x']
            y_scale = self.examples[parent_idx]['y']
            z_scale = self.examples[parent_idx]['z']
            coords_Y = np.transpose(np.where(Y > 0))
            # coords_Y[:, 0] = coords_Y[:, 0] - np.shape(X_orig)[0]/2
            # coords_Y[:, 1] = coords_Y[:, 1] - np.shape(X_orig)[1]/2
            # coords_Y[:, 2] = coords_Y[:, 2] - np.shape(X_orig)[2]/2                
                
            coords_Y[:, 0] = coords_Y[:, 0] + z_scale
            coords_Y[:, 1] = coords_Y[:, 1] + x_scale
            coords_Y[:, 2] = coords_Y[:, 2] + y_scale                
         
                

            stack = np.concatenate((coords_Y, coords_Y_orig))
                            
            unq, count = np.unique(stack, axis=0, return_counts=True)
            duplicated_coords = unq[count>1]
            
            ### scale back down
            duplicated_coords[:, 0] = duplicated_coords[:, 0] - z_scale
            duplicated_coords[:, 1] = duplicated_coords[:, 1] - x_scale
            duplicated_coords[:, 2] = duplicated_coords[:, 2] - y_scale
            
            
            
            ### set to blank:
            Y[duplicated_coords[:, 0], duplicated_coords[:, 1], duplicated_coords[:, 2]] = 0
            
                
            
            """ EVENTUALLY WANT TO ADD IN FULL TRACE but cant right now b/c the TRUTH (Y) is too branchy """

            ### only keep parts of trace that are the parent
            check_with = self.all_orig_idx[all_parent_indices_skip]
            check_with = np.append(check_with, cur_val)
            
            uniq_Y = np.unique(Y)   ### find all values that are unique in the crop
            for uniq_Y in np.unique(Y):
                if uniq_Y not in check_with:
                    Y[Y == uniq_Y] = 0
            parent_trace = seed_crop + Y
            parent_trace[parent_trace > 0] = 1
            
            
            ### OTHERWISE, only use the crop, not the full length                
            #parent_trace = seed_crop

            parent_trace[parent_trace > 0] = 255
            
            
            
            all_parent_im.append(X)
            all_parent_im.append(parent_trace)
            
            
            ### AT MOST ONLY APPEND SO MANY PARENTS
            if len(all_parent_im)/2 == num_parents:
                break
            
            
            ### DEBUG:
            #plot_max(X, ax=0)
            #plot_max(parent_trace, ax=0)

            
        """ If did NOT get enough parents, then append empty arrays """
        num_empty = 0
        while len(all_parent_im)/2 < num_parents:
            all_parent_im.append(np.zeros([self.depth, self.height, self.width]))
            num_empty += 1
            
        #print("num empty: " + str(num_empty))
        
        if len(np.asarray(all_parent_im).shape) == 1:
             print('debug')
                    
                

        return all_parent_im

        """ If want to load parents as well """
  def load_parents(self, index, num_parents, seed_orig, Y_orig):
        ### Find matching tree from all_trees that matches with example
        im_name = self.examples[index]['filename']
        cur_val = self.examples[index]['orig_idx']
        
        match = 0
        for tree in self.all_trees:
            tree_name = tree['im_name']
            tree_size = tree['size']
            #print(tree_name)
            if tree_name in im_name:   ### CHECK BY STRING CONTAINS
                
                parents = get_parents_csv_tree(tree, cur_val, parents = [], num_parents=1000)
                #print('yo')
                match = 1
                break;
                
                
        ### CATCH ERROR if name not matched
        if not match:
            print('ERROR: no name matched')
            print(im_name)
            zzz
                
                
        """ If parents were found: """
        all_parent_im = []
        if np.max(parents) != 0:
                
            """ add current value to list of parents so can include past traces of itself as well 
                    ***maybe move this to before this if statement???
            """
            parents = [cur_val] + parents
            
            ### then search through examples to find matching
            
            ### to save memory, only search through - 10000 examples           
                
            index_beginning_of_im = np.max(np.where(self.all_start_indices < index)[0])
            start_im_num = self.all_start_indices[index_beginning_of_im]
            while len(np.where(self.all_start_indices == start_im_num)[0]) > 0:
                start_im_num -= 1
            start_im_num += 1
                
            search_examples = self.examples[start_im_num:index]
            
            search_example_orig_idx = self.all_orig_idx[start_im_num:index]
            
            
            """ Grab random image from within the parent seed 
            
                    OR actually, get parents exactly 20 pixels apart from each other (i.e. every 4 +/- 1 crops from each other)
            """
            from random import randint
            all_parent_indices = []
            for parent in parents:
                
                if parent != 0:
                    loc_parent = np.where(search_example_orig_idx == parent)[0]
                    #rand_idx = randint(0, len(loc_parent) - 1)
                    #parent_idx = loc_parent[rand_idx] + start_im_num
                    #all_parent_indices.append(parent_idx)
                    
                    all_parent_indices = np.concatenate((all_parent_indices, loc_parent))
                
            all_parent_indices = np.unique(all_parent_indices) ### REMOVE DUPLICATES
            all_parent_indices[::-1].sort()  ### sort into descending order
            
            get_every = 15
            all_parent_indices_skip = []
            for idx, val in enumerate(all_parent_indices):
                rand_idx = randint(-2, 0)
                
                if idx % get_every == 0:           
                    if idx == 0:
                        skip = 1;
                        """ Tiger added ==> skip very first trace!!! otherwise crop seed will be IN THE FOV!!! """
                        # if  idx + 2 < len(all_parent_indices):
                        #     # don't get crop immediately a
                        #     idx = 2
                        # else:                
                        #     all_parent_indices_skip.append(int(all_parent_indices[idx]))
                            
                    else:
                        all_parent_indices_skip.append(int(all_parent_indices[idx + rand_idx]))
                    
                    
                
            #all_parent_indices_skip = all_parent_indices[0::4]  ### get every 4th index
            
            
            """ Get real current crop size!!! so can compare """
            ID = self.list_IDs[index]
    
            input_orig = self.examples[ID]['input']
            # truth_name = self.examples[ID]['truth']
            # seed_name = self.examples[ID]['seed_crop']
    
            X_orig = tifffile.imread(input_orig)
            
            # Y_orig = tifffile.imread(truth_name)
            # seed_orig = tifffile.imread(seed_name)
            # Y[Y > 0] = 1
            # plot_max(Y_orig); plot_max(seed_orig); plot_max(X_orig); plot_max(X); plot_max(Y); plot_max(seed_crop)
            x_scale = self.examples[ID]['x']
            y_scale = self.examples[ID]['y']
            z_scale = self.examples[ID]['z']
            coords_Y_orig = np.transpose(np.where(Y_orig > 0))
            # coords_Y_orig[:, 0] = coords_Y_orig[:, 0] - np.shape(X_orig)[0]/2
            # coords_Y_orig[:, 1] = coords_Y_orig[:, 1] - np.shape(X_orig)[1]/2
            # coords_Y_orig[:, 2] = coords_Y_orig[:, 2] - np.shape(X_orig)[2]/2
            
            coords_Y_orig[:, 0] = coords_Y_orig[:, 0] + z_scale
            coords_Y_orig[:, 1] = coords_Y_orig[:, 1] + x_scale
            coords_Y_orig[:, 2] = coords_Y_orig[:, 2] + y_scale  
            
            coords_Y_orig = expand_coord_to_neighborhood(coords_Y_orig, 3, 4)
            coords_Y_orig = np.unique(coords_Y_orig,axis=0)
                            
            
            """ Scale indices to size of whole list """
            all_parent_indices_skip = all_parent_indices_skip + start_im_num
         
            """ Actually load the parents """         
            for parent_idx in all_parent_indices_skip:
         
                input_name = self.examples[parent_idx]['input']    ### SCALE NUMBER BACK
                truth_name = self.examples[parent_idx]['truth']
                seed_name = self.examples[parent_idx]['seed_crop']
    
                X = tifffile.imread(input_name)
                Y = tifffile.imread(truth_name)
                seed_crop = tifffile.imread(seed_name)
                
                """ Get location """
                x_scale = self.examples[parent_idx]['x']
                y_scale = self.examples[parent_idx]['y']
                z_scale = self.examples[parent_idx]['z']
                coords_Y = np.transpose(np.where(Y > 0))
                # coords_Y[:, 0] = coords_Y[:, 0] - np.shape(X_orig)[0]/2
                # coords_Y[:, 1] = coords_Y[:, 1] - np.shape(X_orig)[1]/2
                # coords_Y[:, 2] = coords_Y[:, 2] - np.shape(X_orig)[2]/2                
                    
                coords_Y[:, 0] = coords_Y[:, 0] + z_scale
                coords_Y[:, 1] = coords_Y[:, 1] + x_scale
                coords_Y[:, 2] = coords_Y[:, 2] + y_scale                
             
                    

                stack = np.concatenate((coords_Y, coords_Y_orig))
                                
                unq, count = np.unique(stack, axis=0, return_counts=True)
                duplicated_coords = unq[count>1]
                
                ### scale back down
                duplicated_coords[:, 0] = duplicated_coords[:, 0] - z_scale
                duplicated_coords[:, 1] = duplicated_coords[:, 1] - x_scale
                duplicated_coords[:, 2] = duplicated_coords[:, 2] - y_scale
                
                
                
                ### set to blank:
                Y[duplicated_coords[:, 0], duplicated_coords[:, 1], duplicated_coords[:, 2]] = 0
                
                    
                
                """ EVENTUALLY WANT TO ADD IN FULL TRACE but cant right now b/c the TRUTH (Y) is too branchy """

                ### only keep parts of trace that are the parent
                check_with = self.all_orig_idx[all_parent_indices_skip]
                check_with = np.append(check_with, cur_val)
                
                uniq_Y = np.unique(Y)   ### find all values that are unique in the crop
                for uniq_Y in np.unique(Y):
                    if uniq_Y not in check_with:
                        Y[Y == uniq_Y] = 0
                parent_trace = seed_crop + Y
                parent_trace[parent_trace > 0] = 1
                
                
                ### OTHERWISE, only use the crop, not the full length                
                #parent_trace = seed_crop

                parent_trace[parent_trace > 0] = 255
                
                
                
                all_parent_im.append(X)
                all_parent_im.append(parent_trace)
                
                
                ### AT MOST ONLY APPEND SO MANY PARENTS
                if len(all_parent_im)/2 == num_parents:
                    break
                
                
                ### DEBUG:
                #plot_max(X, ax=0)
                #plot_max(parent_trace, ax=0)

            
        """ If did NOT get enough parents, then append empty arrays """
        num_empty = 0
        while len(all_parent_im)/2 < num_parents:
            all_parent_im.append(np.zeros([self.depth, self.height, self.width]))
            num_empty += 1
            
        #print("num empty: " + str(num_empty))
        
        if len(np.asarray(all_parent_im).shape) == 1:
             print('debug')
                    
                

        return all_parent_im
               


  def __len__(self):
        'Denotes the total number of samples'
        return len(self.list_IDs)

  def __getitem__(self, index):
        'Generates one sample of data'
        # Select sample
        ID = self.list_IDs[index]

        input_name = self.examples[ID]['input']
        truth_name = self.examples[ID]['truth']
        seed_name = self.examples[ID]['seed_crop']

        X = tifffile.imread(input_name)
        Y = tifffile.imread(truth_name)
        seed_crop = tifffile.imread(seed_name)
        Y[Y > 0] = 1
        
        #crop_size = int(80/2);  ### if want NORMAL XY
        
        
        """ Crop to smaller training data """
        height = X.shape[1]; width = X.shape[2]; depth = X.shape[0]
        
        #crop_size = int(32/2);  ### if want smaller XY
        crop_size = int(64/2);  ### if want smaller XY
        
        z_size = 16
        x = int(X.shape[1]/2 - 1)
        y = int(X.shape[2]/2 - 1)
        z = int(X.shape[0]/2 - 1)
            
        move_im = np.moveaxis(X, 0, -1)
        X_cp, x_min, x_max, y_min, y_max, z_min, z_max = crop_around_centroid(move_im, y, x, z, crop_size=crop_size, z_size=z_size, height=height, width=width, depth=depth)
        X = np.moveaxis(X_cp, -1, 0)
        
        move_im = np.moveaxis(Y, 0, -1)
        Y_cp, x_min, x_max, y_min, y_max, z_min, z_max = crop_around_centroid(move_im, y, x, z, crop_size=crop_size, z_size=z_size, height=height, width=width, depth=depth)
        Y = np.moveaxis(Y_cp, -1, 0)

        move_im = np.moveaxis(seed_crop, 0, -1)
        seed_crop_cp, x_min, x_max, y_min, y_max, z_min, z_max = crop_around_centroid(move_im, y, x, z, crop_size=crop_size, z_size=z_size, height=height, width=width, depth=depth)
        seed_crop = np.moveaxis(seed_crop_cp, -1, 0)        

        ### DEBUG:
        # import napari
        # im = []; im.append(X); im.append(Y * 255); im.append(seed_crop * 255); im = np.asarray(im)
        # im = np.moveaxis(im, 0, -1)
        # with napari.gui_qt():
        #     viewer = napari.view_image(im)

        
        """ Add dilation """
        dil_r = 1
        
        Y = dilate_by_ball_to_binary(Y, radius=dil_r)
        
        seed_crop = dilate_by_ball_to_binary(seed_crop, radius=dil_r)
        
        
        
        """ Resize the z-dimension """
        if self.resize_z:
               X, seed_crop, Y = self.resize_z_func(X, seed_crop, Y)
        
        
        """ Skeletonize """
        if self.skeletonize:
            seed_crop, Y = self.skel(seed_crop, Y)
        
        
        
        """ Get spatial weight matrix """
        if self.sp_weight_bool:
             spatial_weight = self.create_spatial_weight_mat(Y)
             
        elif self.dist_loss:
             spatial_weight = self.create_dist_loss(Y)
        else:
             spatial_weight = []
             
             
           
        
        """ Do normalization here??? """
        #X  = (X  - self.mean)/self.std
        
        """ If want to do transform on CPU """
        if self.transforms:
             X, Y = self.apply_transforms(X, Y)  
        
        """ Append seed mask """
        X = self.append_seed_mask(X, seed_crop) 


        
        """ Get parents for historical context """
        if len(self.all_trees) > 0:
            all_parent_im = self.load_parents(index, self.num_parents, seed_orig=seed_crop, Y_orig=Y)
            all_parent_im = np.asarray(all_parent_im)
            
            if len(all_parent_im.shape) == 1:
                 print('debug')
            
            X = np.concatenate((X, all_parent_im))
            
        elif self.HISTORICAL:
            
            all_parent_im = self.load_HISTORICAL_internodes(index, self.num_parents, seed_orig=seed_crop, Y_orig=Y)
            all_parent_im = np.asarray(all_parent_im)
            
            if len(all_parent_im.shape) == 1:
                 print('debug')
            
            X = np.concatenate((X, all_parent_im))            
            
            
            


        """ If want to do lr_finder """
        # X = np.asarray(X, dtype=np.float32)
        # X = (X - self.mean)/self.std    
        # #X = np.expand_dims(X, axis=0)
        # X = torch.tensor(X, dtype = torch.float, requires_grad=False)
        # Y = torch.tensor(Y, dtype = torch.long, requires_grad=False) 

            
        return X, Y, spatial_weight
















""" Do pre-processing on GPU
          ***can't do augmentation/transforms here because of CPU requirement for torchio

"""
def transfer_to_GPU(X, Y, device, mean, std, transforms = 0):
     """ Put these at beginning later """
     mean = torch.tensor(mean, dtype = torch.float, device=device, requires_grad=False)
     std = torch.tensor(std, dtype = torch.float, device=device, requires_grad=False)
     
     """ Convert to Tensor """
     inputs = torch.tensor(X, dtype = torch.float, device=device, requires_grad=False)
     labels = torch.tensor(Y, dtype = torch.long, device=device, requires_grad=False)           

     """ Normalization """
     inputs = (inputs - mean)/std
                
     """ Expand dims """
     inputs = inputs.unsqueeze(1)   

     return inputs, labels

