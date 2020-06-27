#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun  3 21:21:57 2020

@author: user
"""


import torch
from torch import nn
import torch.nn.functional as F
from switchable_BN import *

__all__ = ['UNet_upsample', 'NestedUNet']


class VGGBlock(nn.Module):
    def __init__(self, in_channels, middle_channels, out_channels, padding, batch_norm_switchable=False):
        super().__init__()
        self.relu = nn.ReLU(inplace=True)
        self.conv1 = nn.Conv3d(in_channels, middle_channels, 5, padding=padding)
        if not batch_norm_switchable:
            self.bn1 = nn.BatchNorm3d(middle_channels)
        else:
            self.sn1 = SwitchNorm3d(middle_channels)


        self.conv2 = nn.Conv3d(middle_channels, out_channels, 5, padding=padding)
        if not batch_norm_switchable:
            self.bn2 = nn.BatchNorm3d(out_channels)
        else:
            self.sn2 = SwitchNorm3d(out_channels)
        self.batch_norm_switchable = batch_norm_switchable

    def forward(self, x):
        out = self.conv1(x)
        out = self.relu(out)        
        if not self.batch_norm_switchable:
            out = self.bn1(out)
        else:
            out = self.sn1(out)

            
        
        
        out = self.conv2(out)
        out = self.relu(out)   # swapped relu to be before the batch norm ***ENABLES LEARNING!!!
        if not self.batch_norm_switchable:
            out = self.bn2(out)
        else:
            out = self.sn2(out)
        return out


    """ For old models without switch norm """
    # def __init__(self, in_channels, middle_channels, out_channels, padding):
    #     super().__init__()
    #     self.relu = nn.ReLU(inplace=True)
    #     self.conv1 = nn.Conv3d(in_channels, middle_channels, 5, padding=padding)
    #     #if not batch_norm_switchable:
    #     self.bn1 = nn.BatchNorm3d(middle_channels)
    #     #else:
    #     #self.sn1 = SwitchNorm3d(middle_channels)


    #     self.conv2 = nn.Conv3d(middle_channels, out_channels, 5, padding=padding)
    #     #if not batch_norm_switchable:
    #     self.bn2 = nn.BatchNorm3d(out_channels)
    #     # else:
    #     #self.sn2 = SwitchNorm3d(out_channels)
    #     #self.batch_norm_switchable = batch_norm_switchable

    # def forward(self, x):
    #     out = self.conv1(x)
    #     out = self.relu(out)        
    #     #if not self.batch_norm_switchable:
    #     out = self.bn1(out)
    #     # else:
    #     #out = self.sn1(out)

       
        
        
    #     out = self.conv2(out)
    #     out = self.relu(out)   # swapped relu to be before the batch norm ***ENABLES LEARNING!!!
    #     #if not self.batch_norm_switchable:
    #     out = self.bn2(out)
    #     #else:
    #     #out = self.sn2(out)
    #     return out



class upsampling(nn.Module):
    def __init__(self, in_channels, out_channels, up_mode='upsample'):
        super().__init__()

        if up_mode == 'upconv':
            self.up = nn.ConvTranspose3d(in_channels, out_channels, kernel_size=2, stride=2, output_padding = 0)
        elif up_mode == 'upsample':
            self.up = nn.Sequential(
                nn.Upsample(mode='trilinear', scale_factor=2),
                nn.Conv3d(in_channels, out_channels, kernel_size=1),
            )
            
            
    def forward(self, x):
        out = self.up(x)

        return out


class UNet_upsample(nn.Module):
    def __init__(self, num_classes, input_channels=3, padding=1, batch_norm_switchable=False, **kwargs):
        super().__init__()

        #nb_filter = [32, 64, 128, 256, 512]
        nb_filter = [16, 32, 64, 128, 256]

        self.up = nn.Upsample(scale_factor=2, mode='trilinear', align_corners=True)

        self.conv0_0 = VGGBlock(input_channels, nb_filter[0], nb_filter[0], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv1_0 = VGGBlock(nb_filter[0], nb_filter[1], nb_filter[1], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv2_0 = VGGBlock(nb_filter[1], nb_filter[2], nb_filter[2], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv3_0 = VGGBlock(nb_filter[2], nb_filter[3], nb_filter[3], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv4_0 = VGGBlock(nb_filter[3], nb_filter[4], nb_filter[4], padding=padding, batch_norm_switchable=batch_norm_switchable)

        self.conv3_1 = VGGBlock(nb_filter[3]+nb_filter[4], nb_filter[3], nb_filter[3], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv2_2 = VGGBlock(nb_filter[2]+nb_filter[3], nb_filter[2], nb_filter[2], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv1_3 = VGGBlock(nb_filter[1]+nb_filter[2], nb_filter[1], nb_filter[1], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv0_4 = VGGBlock(nb_filter[0]+nb_filter[1], nb_filter[0], nb_filter[0], padding=padding, batch_norm_switchable=batch_norm_switchable)

        self.final = nn.Conv3d(nb_filter[0], num_classes, kernel_size=1)




        """ with additional conv during upsampling """
        
        # self.conv0_0 = VGGBlock(input_channels, nb_filter[0], nb_filter[0], padding=padding)
        # self.conv1_0 = VGGBlock(nb_filter[0], nb_filter[1], nb_filter[1], padding=padding)
        # self.conv2_0 = VGGBlock(nb_filter[1], nb_filter[2], nb_filter[2], padding=padding)
        # self.conv3_0 = VGGBlock(nb_filter[2], nb_filter[3], nb_filter[3], padding=padding)
        # self.conv4_0 = VGGBlock(nb_filter[3], nb_filter[4], nb_filter[4], padding=padding)

        # self.up1 = upsampling(nb_filter[4], nb_filter[3], up_mode='upsample')
        # self.conv3_1 = VGGBlock(nb_filter[3]+nb_filter[3], nb_filter[3], nb_filter[3], padding=padding)
        # self.up2 = upsampling(nb_filter[3], nb_filter[2], up_mode='upsample')
        # self.conv2_2 = VGGBlock(nb_filter[2]+nb_filter[2], nb_filter[2], nb_filter[2], padding=padding)
        # self.up3 = upsampling(nb_filter[2], nb_filter[1], up_mode='upsample')
        # self.conv1_3 = VGGBlock(nb_filter[1]+nb_filter[1], nb_filter[1], nb_filter[1], padding=padding)
        # self.up4 = upsampling(nb_filter[1], nb_filter[0], up_mode='upsample')
        # self.conv0_4 = VGGBlock(nb_filter[0]+nb_filter[0], nb_filter[0], nb_filter[0], padding=padding)

        # self.final = nn.Conv3d(nb_filter[0], num_classes, kernel_size=1)


# class UNetUpBlock(nn.Module):
#     def __init__(self, in_size, out_size, up_mode, padding, batch_norm, batch_norm_switchable, kernel_size):
#         super(UNetUpBlock, self).__init__()
#         if up_mode == 'upconv':
#             self.up = nn.ConvTranspose3d(in_size, out_size, kernel_size=2, stride=2, output_padding = 0)
#         elif up_mode == 'upsample':
#             self.up = nn.Sequential(
#                 nn.Upsample(mode='bilinear', scale_factor=2),
#                 nn.Conv3d(in_size, out_size, kernel_size=1),
#             )

#         self.conv_block = UNetConvBlock(out_size * 2, out_size, padding, batch_norm, batch_norm_switchable, kernel_size)

#     def center_crop(self, layer, target_size):
#         _, _, layer_depth, layer_height, layer_width = layer.size()
#         diff_y = (layer_height - target_size[1]) // 2
#         diff_x = (layer_width - target_size[2]) // 2
#         diff_z = (layer_depth - target_size[0]) // 2
#         return layer[
#             :, :, diff_z: (diff_z + target_size[0]), diff_y : (diff_y + target_size[1]), diff_x : (diff_x + target_size[2])
#         ]

#     def forward(self, x, bridge):
#         up = self.up(x)
#         crop1 = self.center_crop(bridge, up.shape[2:])
#         out = torch.cat([up, crop1], 1)
#         out = self.conv_block(out)

#         return out



    def forward(self, input):
        x0_0 = self.conv0_0(input)
        x1_0 = self.conv1_0(F.max_pool3d(x0_0, 2))
        x2_0 = self.conv2_0(F.max_pool3d(x1_0, 2))
        x3_0 = self.conv3_0(F.max_pool3d(x2_0, 2))
        x4_0 = self.conv4_0(F.max_pool3d(x3_0, 2))

        x3_1 = self.conv3_1(torch.cat([x3_0, self.up(x4_0)], 1))
        x2_2 = self.conv2_2(torch.cat([x2_0, self.up(x3_1)], 1))
        x1_3 = self.conv1_3(torch.cat([x1_0, self.up(x2_2)], 1))
        x0_4 = self.conv0_4(torch.cat([x0_0, self.up(x1_3)], 1))


        """ with additional conv during upsampling """
        # x3_1 = self.conv3_1(torch.cat([x3_0, self.up1(x4_0)], 1))
        # x2_2 = self.conv2_2(torch.cat([x2_0, self.up2(x3_1)], 1))
        # x1_3 = self.conv1_3(torch.cat([x1_0, self.up3(x2_2)], 1))
        # x0_4 = self.conv0_4(torch.cat([x0_0, self.up4(x1_3)], 1))



        output = self.final(x0_4)
        return output


class NestedUNet(nn.Module):
    def __init__(self, num_classes, input_channels=3, deep_supervision=False, padding=1, batch_norm_switchable=False, **kwargs):
        super().__init__()

        nb_filter = [32, 64, 128, 256, 512]
        #nb_filter = [16, 32, 64, 128, 256]
        #nb_filter = [8, 16, 32, 64, 128]
        #nb_filter = [4, 8, 16, 32, 64]

        self.deep_supervision = deep_supervision

        #self.pool = nn.MaxPool3d(2, 2, 2)
        self.up = nn.Upsample(scale_factor=2, mode='trilinear', align_corners=True)

        self.conv0_0 = VGGBlock(input_channels, nb_filter[0], nb_filter[0], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv1_0 = VGGBlock(nb_filter[0], nb_filter[1], nb_filter[1], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv2_0 = VGGBlock(nb_filter[1], nb_filter[2], nb_filter[2], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv3_0 = VGGBlock(nb_filter[2], nb_filter[3], nb_filter[3], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv4_0 = VGGBlock(nb_filter[3], nb_filter[4], nb_filter[4], padding=padding, batch_norm_switchable=batch_norm_switchable)

        self.conv0_1 = VGGBlock(nb_filter[0]+nb_filter[1], nb_filter[0], nb_filter[0], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv1_1 = VGGBlock(nb_filter[1]+nb_filter[2], nb_filter[1], nb_filter[1], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv2_1 = VGGBlock(nb_filter[2]+nb_filter[3], nb_filter[2], nb_filter[2], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv3_1 = VGGBlock(nb_filter[3]+nb_filter[4], nb_filter[3], nb_filter[3], padding=padding, batch_norm_switchable=batch_norm_switchable)

        self.conv0_2 = VGGBlock(nb_filter[0]*2+nb_filter[1], nb_filter[0], nb_filter[0], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv1_2 = VGGBlock(nb_filter[1]*2+nb_filter[2], nb_filter[1], nb_filter[1], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv2_2 = VGGBlock(nb_filter[2]*2+nb_filter[3], nb_filter[2], nb_filter[2], padding=padding, batch_norm_switchable=batch_norm_switchable)

        self.conv0_3 = VGGBlock(nb_filter[0]*3+nb_filter[1], nb_filter[0], nb_filter[0], padding=padding, batch_norm_switchable=batch_norm_switchable)
        self.conv1_3 = VGGBlock(nb_filter[1]*3+nb_filter[2], nb_filter[1], nb_filter[1], padding=padding, batch_norm_switchable=batch_norm_switchable)

        self.conv0_4 = VGGBlock(nb_filter[0]*4+nb_filter[1], nb_filter[0], nb_filter[0], padding=padding, batch_norm_switchable=batch_norm_switchable)

        if self.deep_supervision:
            self.final1 = nn.Conv3d(nb_filter[0], num_classes, kernel_size=1)
            self.final2 = nn.Conv3d(nb_filter[0], num_classes, kernel_size=1)
            self.final3 = nn.Conv3d(nb_filter[0], num_classes, kernel_size=1)
            self.final4 = nn.Conv3d(nb_filter[0], num_classes, kernel_size=1)
        else:
            self.final = nn.Conv3d(nb_filter[0], num_classes, kernel_size=1)


    def forward(self, input):
        x0_0 = self.conv0_0(input)
        x1_0 = self.conv1_0(F.max_pool3d(x0_0, 2))
        x0_1 = self.conv0_1(torch.cat([x0_0, self.up(x1_0)], 1))

        x2_0 = self.conv2_0(F.max_pool3d(x1_0, 2))
        x1_1 = self.conv1_1(torch.cat([x1_0, self.up(x2_0)], 1))
        x0_2 = self.conv0_2(torch.cat([x0_0, x0_1, self.up(x1_1)], 1))

        x3_0 = self.conv3_0(F.max_pool3d(x2_0, 2))
        x2_1 = self.conv2_1(torch.cat([x2_0, self.up(x3_0)], 1))
        x1_2 = self.conv1_2(torch.cat([x1_0, x1_1, self.up(x2_1)], 1))
        x0_3 = self.conv0_3(torch.cat([x0_0, x0_1, x0_2, self.up(x1_2)], 1))

        x4_0 = self.conv4_0(F.max_pool3d(x3_0, 2))
        x3_1 = self.conv3_1(torch.cat([x3_0, self.up(x4_0)], 1))
        x2_2 = self.conv2_2(torch.cat([x2_0, x2_1, self.up(x3_1)], 1))
        x1_3 = self.conv1_3(torch.cat([x1_0, x1_1, x1_2, self.up(x2_2)], 1))
        x0_4 = self.conv0_4(torch.cat([x0_0, x0_1, x0_2, x0_3, self.up(x1_3)], 1))
        
        
        
        # x0_0 = self.conv0_0(input)
        # x1_0 = self.conv1_0(self.pool(x0_0))
        # x0_1 = self.conv0_1(torch.cat([x0_0, self.up(x1_0)], 1))

        # x2_0 = self.conv2_0(self.pool(x1_0))
        # x1_1 = self.conv1_1(torch.cat([x1_0, self.up(x2_0)], 1))
        # x0_2 = self.conv0_2(torch.cat([x0_0, x0_1, self.up(x1_1)], 1))

        # x3_0 = self.conv3_0(self.pool(x2_0))
        # x2_1 = self.conv2_1(torch.cat([x2_0, self.up(x3_0)], 1))
        # x1_2 = self.conv1_2(torch.cat([x1_0, x1_1, self.up(x2_1)], 1))
        # x0_3 = self.conv0_3(torch.cat([x0_0, x0_1, x0_2, self.up(x1_2)], 1))

        # x4_0 = self.conv4_0(self.pool(x3_0))
        # x3_1 = self.conv3_1(torch.cat([x3_0, self.up(x4_0)], 1))
        # x2_2 = self.conv2_2(torch.cat([x2_0, x2_1, self.up(x3_1)], 1))
        # x1_3 = self.conv1_3(torch.cat([x1_0, x1_1, x1_2, self.up(x2_2)], 1))
        # x0_4 = self.conv0_4(torch.cat([x0_0, x0_1, x0_2, x0_3, self.up(x1_3)], 1))
        
        
        

        if self.deep_supervision:
            output1 = self.final1(x0_1)
            output2 = self.final2(x0_2)
            output3 = self.final3(x0_3)
            output4 = self.final4(x0_4)
            return [output1, output2, output3, output4]

        else:
            output = self.final(x0_4)
            return output