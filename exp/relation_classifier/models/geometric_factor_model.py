import torch
import copy
import torch.nn as nn
from torch.autograd import Variable

import utils.io as io
import utils.pytorch_layers as pytorch_layers


class GeometricFactorConstants(io.JsonSerializableClass):
    def __init__(self):
        super(GeometricFactorConstants,self).__init__()
        self.box_feat_size = 24
        self.out_dim = 117

    @property
    def box_feature_factor_const(self):
        factor_const = {
            'in_dim': self.box_feat_size,
            'out_dim': self.out_dim,
            'out_activation': 'Identity',
            'layer_units': [],
            'activation': 'ReLU',
            'use_out_bn': False,
            'use_bn': True
        }
        return factor_const
    
    
class GeometricFactor(nn.Module,io.WritableToFile):
    def __init__(self,const):
        super(GeometricFactor,self).__init__()
        self.const = copy.deepcopy(const)
        self.box_feature_factor = pytorch_layers.create_mlp(
            self.const.box_feature_factor_const)

    def forward(self,feats):
        box_feature_factor_scores = self.box_feature_factor(feats['box'])
        return box_feature_factor_scores


class GeometricFactorPairwiseConstants(GeometricFactorConstants):
    def __init__(self):
        super(GeometricFactorPairwiseConstants,self).__init__()

    @property
    def pairwise_linear_const(self):
        const = {
            'in_dim': self.box_feat_size**2,
            'out_dim': 2000,
        }
        return const

    @property
    def agg_linear_const(self):
        const = {
            'in_dim': self.pairwise_linear_const['out_dim']+self.box_feat_size,
            'out_dim': self.out_dim,
        }
        return const
    

class GeometricFactorPairwise(nn.Module,io.WritableToFile):
    def __init__(self,const):
        super(GeometricFactorPairwise,self).__init__()
        self.const = copy.deepcopy(const)
        
        self.box_feat_bn = nn.BatchNorm2d(self.const.box_feat_size)

        pairwise_linear_const = self.const.pairwise_linear_const
        self.pairwise_linear = nn.Linear(
            pairwise_linear_const['in_dim'],
            pairwise_linear_const['out_dim'])
        
        self.pairwise_bn = nn.BatchNorm2d(pairwise_linear_const['out_dim'])
        
        agg_linear_const = self.const.agg_linear_const
        self.agg_linear = nn.Linear(
            agg_linear_const['in_dim'],
            agg_linear_const['out_dim'])

    def get_pairwise_feat(self,x):
        """
        x is B x F
        """
        B,F = x.size()
        x1 = x.view(B,F,1).repeat(1,1,F)
        x2 = x.view(B,1,F).repeat(1,F,1)
        y = x2-x1
        y = y.view(B,-1) # B x F*F
        return y
    
    def forward(self,feats):
        pairwise_feats = self.get_pairwise_feat(feats['box'])
        pairwise_feats = self.pairwise_linear(pairwise_feats)
        pairwise_feats = self.pairwise_bn(pairwise_feats)
        box_feat = self.box_feat_bn(feats['box'])
        agg_feats = torch.cat((box_feat,pairwise_feats*pairwise_feats),1)
        box_feature_factor_scores = self.agg_linear(agg_feats)
        return box_feature_factor_scores