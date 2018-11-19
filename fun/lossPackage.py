import torch 
import torch.nn as nn
import torch.nn.functional as F
import pdb
import time

class HLoss(nn.Module):
    def __init__(self):
        super(HLoss, self).__init__()

    def forward(self, x):
        b = F.softmax(x, dim=1) * F.log_softmax(x, dim=1)
        b = -1.0 * b.sum(dim=1)
        b = torch.mean(b)
        return b

class lossEvaluator(nn.Module):
    def __init__(self, margin=0.1, biLossFlag=True, lossWFlag=False, lamda=0.8, struct_flag=False, struct_only_flag=False, entropy_regu_flag=False, lamda2=0.1):
        super(lossEvaluator, self).__init__()
        self.margin =margin
        self.biLossFlag = biLossFlag
        self.lossWFlag = lossWFlag
        self.lamda= lamda
        self.struct_flag = struct_flag
        self.struct_only_flag = struct_only_flag
        self.entropy_regu_flag = entropy_regu_flag
        self.lamda2 = lamda2
        if self.entropy_regu_flag:
            self.entropy_calculator = HLoss()

    def forward(self, imFtr=None, disFtr=None, lblList=None, simMM=None):
        if self.lossWFlag:
            loss = self.forwardRankW_v2(imFtr, disFtr, lblList)
            return loss
        if self.wsMode=='rankTube' or self.wsMode=='rankFrm':
            loss = self.forwardRank(imFtr, disFtr, lblList)
        elif self.wsMode=='coAtt' or self.wsMode =='coAttV2' or self.wsMode=='coAttV3' or self.wsMode=='coAttV4':
            loss = self.forwardCoAtt(simMM, lblList)
        return loss

    def forwardRank(self, imFtr, disFtr, lblList):
        disFtr = disFtr.squeeze()
        bSize = len(lblList)
        if(len(lblList)==1):
            return torch.zeros(1).cuda()
        imFtr = imFtr.view(-1, imFtr.shape[2])
        simMM = torch.mm(imFtr, disFtr.transpose(0, 1))
        simMMRe = simMM.view(bSize, -1, bSize)
        simMax, maxIdx= torch.max(simMMRe, dim=1)
        loss = torch.zeros(1).cuda()
        pairNum = 0.000001

#        pdb.set_trace()
        t1 = time.time()
        #print(lblList)
        if not self.struct_only_flag:
            for i, lblIm in enumerate(lblList):
                posSim = simMax[i, i]
                for j, lblTxt in enumerate(lblList):
                    if(lblIm==lblTxt):
                        continue
                    else:
                        tmpLoss = simMax[i, j] - posSim + self.margin
                        pairNum +=1
                        if(tmpLoss>0):
                            loss +=tmpLoss
            loss = loss/pairNum

        if self.biLossFlag and not self.struct_only_flag:
            lossBi = torch.zeros(1).cuda()
            pairNum =0.000001
            for i, lblTxt in enumerate(lblList):
                posSim = simMax[i, i]
                for j, lblIm in enumerate(lblList):
                    if(lblIm==lblTxt):
                        continue
                    else:
                        tmpLoss = simMax[j, i] - posSim + self.margin
                        pairNum +=1
                        if(tmpLoss>0):
                            lossBi +=tmpLoss
            if pairNum>0:
                loss +=lossBi/pairNum
        t2 = time.time()
        #print(t2-t1)
        if self.struct_flag:
           # select most similar regions from the tubes
            imFtr = imFtr.view(bSize, -1, imFtr.shape[1])
            tube_ftr_list = [ imFtr[i, int(maxIdx[i, i]), ...] for i in range(bSize)]
            tube_ftr_tensor = torch.stack(tube_ftr_list, 0)
            vis_ftr_struct_sim = torch.mm(tube_ftr_tensor, tube_ftr_tensor.transpose(0, 1))
            txt_ftr_struct_sim = torch.mm(disFtr, disFtr.transpose(0, 1))
            sim_res_mat = vis_ftr_struct_sim - txt_ftr_struct_sim
            sim_res_mat_pow2 = torch.pow(sim_res_mat, 2)
            sim_res_mat_pow2_sqrt = torch.sqrt(sim_res_mat_pow2 + torch.ones(bSize, bSize).cuda()*0.000001)
            #sim_res_mat_pow2_sqrt = sim_res_mat_pow2
            sim_res_l2_loss = sim_res_mat_pow2_sqrt.sum()/(bSize*bSize-bSize)
            print('biloss %3f, struct loss %3f ' %(float(loss), float(sim_res_l2_loss)))            
            loss += self.lamda*sim_res_l2_loss

        if self.entropy_regu_flag:
            #simMMRe = simMM.view(bSize, -1, bSize)
            # simMMRe: bSize, prpNum, bSize
            ftr_match_pair_list = list()
            ftr_unmatch_pair_list = list()

            for i in range(bSize):
                for j in range(bSize):
                    if i==j:
                        ftr_match_pair_list.append(simMMRe[i, ..., i])
                    elif lblList[i]!=lblList[j]:
                        ftr_unmatch_pair_list.append(simMMRe[i, ..., j])

            ftr_match_pair_mat = torch.stack(ftr_match_pair_list, 0)
            ftr_unmatch_pair_mat = torch.stack(ftr_unmatch_pair_list, 0)
            match_num = len(ftr_match_pair_list)
            unmatch_num = len(ftr_unmatch_pair_list)
            if match_num>0:
                entro_loss = self.entropy_calculator(ftr_match_pair_mat)
            loss +=self.lamda2*entro_loss 
            print('entropy loss: %3f ' %(float(entro_loss)))
            #pdb.set_trace()
        print('\n')
        return loss

    def forwardCoAtt(self, simMMRe, lblList):
        bSize = len(lblList)
        if(len(lblList)==1):
            return torch.zeros(1).cuda()
        simMax, maxIdx= torch.max(simMMRe, dim=1)
        loss = torch.zeros(1).cuda()
        pairNum = 0.000001

#        pdb.set_trace()
        t1 = time.time()
        #print(lblList)
        if not self.struct_only_flag:
            for i, lblIm in enumerate(lblList):
                posSim = simMax[i, i]
                for j, lblTxt in enumerate(lblList):
                    if(lblIm==lblTxt):
                        continue
                    else:
                        tmpLoss = simMax[i, j] - posSim + self.margin
                        pairNum +=1
                        if(tmpLoss>0):
                            loss +=tmpLoss
            loss = loss/pairNum

        if self.biLossFlag and not self.struct_only_flag:
            lossBi = torch.zeros(1).cuda()
            pairNum =0.000001
            for i, lblTxt in enumerate(lblList):
                posSim = simMax[i, i]
                for j, lblIm in enumerate(lblList):
                    if(lblIm==lblTxt):
                        continue
                    else:
                        tmpLoss = simMax[j, i] - posSim + self.margin
                        pairNum +=1
                        if(tmpLoss>0):
                            lossBi +=tmpLoss
            if pairNum>0:
                loss +=lossBi/pairNum
        t2 = time.time()

        if self.entropy_regu_flag:
            #simMMRe = simMM.view(bSize, -1, bSize)
            # simMMRe: bSize, prpNum, bSize
            simMMRe = simMMRe.squeeze()
            ftr_match_pair_list = list()
            ftr_unmatch_pair_list = list()

            for i in range(bSize):
                for j in range(bSize):
                    if i==j:
                        ftr_match_pair_list.append(simMMRe[i, ..., i])
                    elif lblList[i]!=lblList[j]:
                        ftr_unmatch_pair_list.append(simMMRe[i, ..., j])

            ftr_match_pair_mat = torch.stack(ftr_match_pair_list, 0)
            ftr_unmatch_pair_mat = torch.stack(ftr_unmatch_pair_list, 0)
            match_num = len(ftr_match_pair_list)
            unmatch_num = len(ftr_unmatch_pair_list)
            if match_num>0:
                entro_loss = self.entropy_calculator(ftr_match_pair_mat)
            loss +=self.lamda2*entro_loss 
            print('entropy loss: %3f ' %(float(entro_loss)))
            #pdb.set_trace()
        print('\n')
        return loss

    def forwardRankW(self, imFtr, disFtr, lblList):
        disFtr = disFtr.squeeze()
        bSize = len(lblList)
        if(len(lblList)==1):
            return torch.zeros(1).cuda()
#        pdb.set_trace()
        imFtr = imFtr.view(-1, imFtr.shape[2])
        simMM = torch.mm(imFtr, disFtr.transpose(0, 1))
        simMMRe = simMM.view(bSize, -1, bSize)
        simMax, maxIdx= torch.max(simMMRe, dim=1)
        simMax = F.sigmoid(simMax)
        DMtr = -2*torch.log10(simMax)
        loss = torch.zeros(1).cuda()
        pairNum = 0
        for i, lblIm in enumerate(lblList):
            posSim = simMax[i, i]
            for j, lblTxt in enumerate(lblList):
                if(lblIm==lblTxt):
                    continue
                else:
                    tmpLoss = simMax[i, j] - posSim + self.margin
                    pairNum +=1
                    if(tmpLoss>0):
                        loss +=tmpLoss*self.lamda*posSim
                    loss +=(1-self.lamda)*DMtr[i, i]
        loss = loss/(pairNum+0.000001)

        if self.biLossFlag:
            lossBi = torch.zeros(1).cuda()
            pairNum =0
            for i, lblTxt in enumerate(lblList):
                posSim = simMax[i, i]
                for j, lblIm in enumerate(lblList):
                    if(lblIm==lblTxt):
                        continue
                    else:
                        tmpLoss = simMax[j, i] - posSim + self.margin
                        pairNum +=1
                        if(tmpLoss>0):
                            lossBi +=tmpLoss*self.lamda*posSim
            if pairNum>0:
                loss +=lossBi/(0.000001+pairNum)
        return loss

    def forwardRankW_v2(self, imFtr, disFtr, lblList):
        disFtr = disFtr.squeeze()
        bSize = len(lblList)
        if(len(lblList)==1):
            return torch.zeros(1).cuda()
#        pdb.set_trace()
        imFtr = imFtr.view(-1, imFtr.shape[2])
        simMM = torch.mm(imFtr, disFtr.transpose(0, 1))
        simMMRe = simMM.view(bSize, -1, bSize)
        simMax, maxIdx= torch.max(simMMRe, dim=1)
        simMax = F.sigmoid(simMax)
        DMtr = -2*torch.log10(simMax)
        loss = torch.zeros(1).cuda()
        pairNum = 0
        for i, lblIm in enumerate(lblList):
            posSim = simMax[i, i]
            tmp_frm_loss = 0
            for j, lblTxt in enumerate(lblList):
                if(lblIm==lblTxt):
                    continue
                else:
                    tmpLoss = simMax[i, j] - posSim + self.margin
                    if(tmpLoss>0):
                        tmp_frm_loss +=tmpLoss*self.lamda*posSim

            for j, lblIm in enumerate(lblList):
                    if(lblIm==lblTxt):
                        continue
                    else:
                        tmpLoss = simMax[j, i] - posSim + self.margin
                        #pairNum +=1
                        if(tmpLoss>0):
                            tmp_frm_loss +=tmpLoss*self.lamda*posSim
            loss +=(1-self.lamda)*DMtr[i, i]
            pairNum +=1
            loss +=tmp_frm_loss
        loss = loss/(pairNum+0.000001)
        return loss

class lossGroundR(nn.Module):
    def __init__(self, entropy_regu_flag=False, lamda2=0):
        super(lossGroundR, self).__init__()
        #pdb.set_trace()  
        self.criterion = nn.CrossEntropyLoss()
        if  entropy_regu_flag:
            self.entropy_regu_flag= True
            self.entropy_calculator = HLoss()
            self.lamda2 =lamda2
        else:
            self.entropy_regu_flag= False
    
    def forward(self, logMat, wordLbl, simMM=None, lblList=None):
#        pdb.set_trace()

#       pdb.set_trace()
        loss = 0
        bSize = len(wordLbl)
        for i in range(bSize):
            assert len(wordLbl[i])==1
            wL = len(wordLbl[i][0])
            tmpPredict = logMat[i, :wL, :]
            loss += self.criterion(tmpPredict, torch.LongTensor(wordLbl[i][0]).cuda())

        loss = loss/(bSize+0.00001) #  loss nomalization
        # regulation loss
        if self.entropy_regu_flag and simMM is not None:
            #simMMRe = simMM.view(bSize, -1, bSize)
            # simMMRe: bSize, prpNum, bSize
            simMMRe = simMM.squeeze()
            ftr_match_pair_list = list()
            ftr_unmatch_pair_list = list()
            bSize = simMM.shape[0]
            for i in range(bSize):
                for j in range(bSize):
                    if i==j:
                        ftr_match_pair_list.append(simMMRe[i, ..., i])
                    elif lblList[i]!=lblList[j]:
                        ftr_unmatch_pair_list.append(simMMRe[i, ..., j])

            ftr_match_pair_mat = torch.stack(ftr_match_pair_list, 0)
            ftr_unmatch_pair_mat = torch.stack(ftr_unmatch_pair_list, 0)
            match_num = len(ftr_match_pair_list)
            unmatch_num = len(ftr_unmatch_pair_list)
            if match_num>0:
                entro_loss = self.entropy_calculator(ftr_match_pair_mat)
            loss +=self.lamda2*entro_loss 
            print('entropy loss: %3f ' %(float(entro_loss)))
        
        return loss

def build_lossEval(opts):
    if opts.wsMode == 'rankTube' or opts.wsMode=='coAtt' or opts.wsMode=='coAttV2' or opts.wsMode=='coAttV3' or opts.wsMode == 'coAttV4' or  opts.wsMode=='rankFrm':
        loss_criterion = lossEvaluator(opts.margin, opts.biLoss, opts.lossW, \
                opts.lamda, opts.struct_flag, opts.struct_only, \
                opts.entropy_regu_flag, opts.lamda2)
        loss_criterion.wsMode =opts.wsMode
        return loss_criterion
    elif opts.wsMode =='rankGroundR' or opts.wsMode =='coAttGroundR' or opts.wsMode=='rankGroundRV2':
        loss_criterion = lossGroundR(entropy_regu_flag=opts.entropy_regu_flag, \
               lamda2=opts.lamda2 )
        loss_criterion.wsMode = opts.wsMode
        return loss_criterion
