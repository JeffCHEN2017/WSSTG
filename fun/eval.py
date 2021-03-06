from wsParamParser import parse_args
from data.data_loader  import* 
from datasetLoader import *
from modelArc import *
from optimizers import *
from logInfo import logInF
from lossPackage import *
from netUtil import *
from tensorboardX import SummaryWriter
import time

import pdb

if __name__=='__main__':
    opt = parse_args()
    # build dataloader
    dataLoader, datasetOri= build_dataloader(opt) 
    # build network 
    model = build_network(opt)
    # build_optimizer
    logger = logInF(opt.logFd)
    ep = 0
    #thre_list = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    thre_list = [0.5]
    acc_list = list()
    more_detailed_flag = True
    for thre in thre_list:
        acc_list.append([])

    if opt.eval_val_flag:
        model.eval()
        resultList = list()
        vIdList = list()
        set_name_ori= opt.set_name
        opt.set_name = 'val'
        dataLoaderEval, datasetEvalOri = build_dataloader(opt) 
        for itr_eval, inputData in enumerate(dataLoaderEval):
            tube_embedding, cap_embedding, tubeInfo, indexOri, cap_length_list, vd_name_list, word_lbl_list = inputData
            dataIdx = None
            b_size = tube_embedding.shape[0]
            # B*P*T*D
            imDis = tube_embedding.cuda()
            imDis = imDis.view(-1, imDis.shape[2], imDis.shape[3])
            wordEmb = cap_embedding.cuda()
            wordEmb = wordEmb.view(-1, wordEmb.shape[2], wordEmb.shape[3])
            imDis.requires_grad=False
            wordEmb.requires_grad=False
            
            if opt.wsMode =='coAtt':
                simMM = model(imDis, wordEmb, cap_length_list)
                #pdb.set_trace()
                simMM = simMM.view(b_size, opt.rpNum)            
                for i, thre in enumerate(thre_list):
                    acc_list[i] += evalAcc_att_test(simMM, tubeInfo, indexOri, datasetEvalOri, opt.visRsFd+str(ep), False, topK=1, thre_list=[thre], more_detailed_flag=more_detailed_flag)
                
        for i, thre in enumerate(thre_list):
            resultList = acc_list[i]
            accSum = 0
            for ele in resultList:
                recall_k= ele[1]
                accSum +=recall_k
            logger('thre @ %f, Average accuracy on validation set is %3f\n' %(thre, accSum/len(resultList)))
        
        out_result_fn = opt.logFd + 'result_val_' +os.path.basename(opt.initmodel).split('.')[0] + '.pk'
        pickledump(out_result_fn, acc_list)

    if opt.eval_test_flag:
        model.eval()
        resultList = list()
        vIdList = list()
        set_name_ori= opt.set_name
        opt.set_name = 'test'
        dataLoaderEval, datasetEvalOri = build_dataloader(opt) 
        #pdb.set_trace()
        for itr_eval, inputData in enumerate(dataLoaderEval):
            tube_embedding, cap_embedding, tubeInfo, indexOri, cap_length_list, vd_name_list, word_lbl_list = inputData
            dataIdx = None
            b_size = tube_embedding.shape[0]
            # B*P*T*D
            imDis = tube_embedding.cuda()
            imDis = imDis.view(-1, imDis.shape[2], imDis.shape[3])
            wordEmb = cap_embedding.cuda()
            wordEmb = wordEmb.view(-1, wordEmb.shape[2], wordEmb.shape[3])
            imDis.requires_grad=False
            wordEmb.requires_grad=False
            
            if opt.wsMode =='coAtt':
                simMM = model(imDis, wordEmb, cap_length_list)
                simMM = simMM.view(b_size, opt.rpNum)            
                for i, thre in enumerate(thre_list):
                    acc_list[i] += evalAcc_att_test(simMM, tubeInfo, indexOri, datasetEvalOri, opt.visRsFd+str(ep), False, thre_list=[thre], more_detailed_flag=more_detailed_flag)

        for i, thre in enumerate(thre_list):
            resultList = acc_list[i]
            accSum = 0
            for ele in resultList:
                recall_k= ele[1]
                accSum +=recall_k
            logger('thre @ %f, Average accuracy on testing set is %3f\n' %(thre, accSum/len(resultList)))
        out_result_fn = opt.logFd + 'result_test_' +os.path.basename(opt.initmodel).split('.')[0] + '.pk'
        pickledump(out_result_fn, acc_list)
        
