import os
import torch
import shutil
import sys
import pdb
#from evalDet import *
sys.path.append('..')
from util.mytoolbox import *
from image_toolbox import *

def visTube_from_image(frmList, tube, outName):
    image_list   = list()
    for i, bbx in enumerate(tube):
        imName = frmList[i]
        img = draw_rectangle(imName, bbx)
        image_list.append(img)
        images2video(image_list, 10, outName)

def vis_image_bbx(frmList, tube, color=(0,0,255), thickness=3, dotted=False):
    image_list   = list()
    for i, bbx in enumerate(tube):
        imName = frmList[i]
        img = draw_rectangle(imName, bbx, color, thickness, dotted)
        image_list.append(img)
    return image_list

def vis_gray_but_bbx(frmList, tube):
    image_list   = list()
    for i, bbx in enumerate(tube):
        imName = frmList[i]
        img = gray_background(imName, bbx)
        image_list.append(img)
    return image_list



KEYS = ['x1', 'y1', 'x2', 'y2']
def compute_IoU(box1, box2):
    if isinstance(box1, list):
        box1 = {key: val for key, val in zip(KEYS, box1)}
    if isinstance(box2, list):
        box2 = {key: val for key, val in zip(KEYS, box2)}
    width = max(min(box1['x2'], box2['x2']) - max(box1['x1'], box2['x1']), 0)
    height = max(min(box1['y2'], box2['y2']) - max(box1['y1'], box2['y1']), 0)
    intersection = width * height
    box1_area = (box1['x2'] - box1['x1']) * (box1['y2'] - box1['y1'])
    box2_area = (box2['x2'] - box2['x1']) * (box2['y2'] - box2['y1'])
    union = box1_area + box2_area - intersection
    return float(intersection) / (float(union) +0.000001)  # avoid overthow


EPS = 1e-10
def compute_IoU_v2(bbox1, bbox2):
    bbox1_area = float((bbox1[2] - bbox1[0] + EPS) * (bbox1[3] - bbox1[1] + EPS))
    bbox2_area = float((bbox2[2] - bbox2[0] + EPS) * (bbox2[3] - bbox2[1] + EPS))
    w = max(0.0, min(bbox1[2], bbox2[2]) - max(bbox1[0], bbox2[0]) + EPS)
    h = max(0.0, min(bbox1[3], bbox2[3]) - max(bbox1[1], bbox2[1]) + EPS)
    inter = float(w * h)
    ovr = inter / (bbox1_area + bbox2_area - inter)
    return ovr

def is_annotated(traj, frame_ind):
    if not frame_ind in traj:
        return False
    box = traj[frame_ind]
    if box[0] < 0:
        for el_val in box[1:]:
            assert el_val < 0
        return False
    for el_val in box[1:]:
        assert el_val >= 0
    return True

def compute_LS(traj, gt_traj):
    # see http://jvgemert.github.io/pub/jain-tubelets-cvpr2014.pdf
    assert isinstance(traj.keys()[0], type(gt_traj.keys()[0]))
    IoU_list = []
    for frame_ind, gt_box in gt_traj.iteritems():
        gt_is_annotated = is_annotated(gt_traj, frame_ind)
        pr_is_annotated = is_annotated(traj, frame_ind)
        if (not gt_is_annotated) and (not pr_is_annotated):
            continue
        if (not gt_is_annotated) or (not pr_is_annotated):
            IoU_list.append(0.0)
            continue
        box = traj[frame_ind]
        IoU_list.append(compute_IoU_v2(box, gt_box))
    return sum(IoU_list) / len(IoU_list)

def get_tubes(det_list_org, alpha):
    det_list = copy.deepcopy(det_list_org)
    tubes = []
    continue_flg = True
    tube_scores = []
    while continue_flg:
        timestep = 0
        score_list = []
        score_list.append(np.zeros(det_list[timestep][0].shape[0]))
        prevind_list = []
        prevind_list.append([-1] * det_list[timestep][0].shape[0])
        timestep += 1
        while timestep < len(det_list):
            n_curbox = det_list[timestep][0].shape[0]
            n_prevbox = score_list[-1].shape[0]
            cur_scores = np.zeros(n_curbox) - np.inf
            prev_inds = [-1] * n_curbox
            for i_prevbox in range(n_prevbox):
                prevbox_coods = det_list[timestep-1][1][i_prevbox, :]
                prevbox_score = det_list[timestep-1][0][i_prevbox, 0]
                for i_curbox in range(n_curbox):
                    curbox_coods = det_list[timestep][1][i_curbox, :]
                    curbox_score = det_list[timestep][0][i_curbox, 0]
                    try:
                        e_score = compute_IoU(prevbox_coods.tolist(), curbox_coods.tolist())
                    except:
                        pdb.set_trace()
                    link_score = prevbox_score + curbox_score + alpha * e_score
                    cur_score = score_list[-1][i_prevbox] + link_score
                    if cur_score > cur_scores[i_curbox]:
                        cur_scores[i_curbox] = cur_score
                        prev_inds[i_curbox] = i_prevbox
            score_list.append(cur_scores)
            prevind_list.append(prev_inds)
            timestep += 1

        # get path and remove used boxes
        cur_tube = [None] * len(det_list)
        tube_score = np.max(score_list[-1]) / len(det_list)
        prev_ind = np.argmax(score_list[-1])
        timestep = len(det_list) - 1
        while timestep >= 0:
            cur_tube[timestep] = det_list[timestep][1][prev_ind, :].tolist()
            det_list[timestep][0] = np.delete(det_list[timestep][0], prev_ind, axis=0)
            det_list[timestep][1] = np.delete(det_list[timestep][1], prev_ind, axis=0)
            prev_ind = prevind_list[timestep][prev_ind]
            if det_list[timestep][1].shape[0] == 0:
                continue_flg = False
            timestep -= 1
        assert prev_ind < 0
        tubes.append(cur_tube)
        tube_scores.append(tube_score)
    return tubes, tube_scores

def save_check_point(state, is_best=False, file_name='../data/models/checkpoint.pth'):
    fdName = os.path.dirname(file_name)
    makedirs_if_missing(fdName)
    torch.save(state, file_name)
    if is_best:
        shutil.copyfile(file_name, '../data/model/best_model.pth')

def load_model_state(model, file_name):
    states = torch.load(file_name)
    model.load_state_dict(states)

def visRelations(annDict, lblVideo, prpList, frmList, gtBbxList, capLbl, fdPre, aff_softmax, \
        aff_scale, aff_weight):
    topK = 10
    bSize = len(prpList)
    frmSize = len(prpList[0])
    prpSize = len(prpList[0][0])
    aff_softmax = aff_softmax.view(bSize, frmSize, prpSize, -1, frmSize*prpSize)
    aff_scale = aff_scale.view(bSize, frmSize, prpSize, -1, frmSize*prpSize)
    aff_weight = aff_weight.view(bSize, frmSize, prpSize, -1, frmSize*prpSize)
    for bId  in range(bSize):
        lbl = capLbl[bId]
        vdName = annDict['vd'][lbl]
        
        for fii, fId in enumerate(frmList[bId]): 
            if fii!=(frmSize-1)/2:
                continue
            #imFullPath  = '/data1/zfchen/data/A2D/Release/pngs320H/'  \
            #        + vdName +'/'+ annDict['frmList'][lbl][fId] +'.png'
            #img = cv2.imread(imFullPath)
            # load img ilist
            #imgList  = list()
            #for fId2 in frmList[bId]:
            #    imFullPath  = '/data1/zfchen/data/A2D/Release/pngs320H/'  \
            #            + vdName +'/'+ annDict['frmList'][lbl][fId2] +'.png'
            #    img2 = cv2.imread(imFullPath)
            #    imgList.append(img2)
    
            #draw Knn
            for pii, prpBox in enumerate(prpList[bId][fii]):
                if pii>=1:
                    continue
                imgList  = list()
                for fId2 in frmList[bId]:
                    imFullPath  = '/data1/zfchen/data/A2D/Release/pngs320H/'  \
                            + vdName +'/'+ annDict['frmList'][lbl][fId] +'.png'
                    img = cv2.imread(imFullPath)
                    imFullPath  = '/data1/zfchen/data/A2D/Release/pngs320H/'  \
                            + vdName +'/'+ annDict['frmList'][lbl][fId2] +'.png'
                    img2 = cv2.imread(imFullPath)
                    imgList.append(img2)
                pdb.set_trace()
                aff_scale_bfp = torch.sum(aff_softmax[bId, fii, pii, :, :], dim=0)
                #aff_scale_bfp = aff_softmax[bId, fii, pii, 0, :]
                #aff_scale_bfp = torch.sum(aff_weight[bId, fii, pii, :, :], dim=0)
                #aff_scale_bfp = torch.sum(aff_scale[bId, fii, pii, :, :], dim=0)
                rsVMat, sortIdx =  torch.sort(aff_scale_bfp, dim=0, descending=True)
                for kId in range(topK):
                    #pdb.set_trace()
                    rsV = float(rsVMat[kId].data.cpu()[0])
                    prpRsId = int(sortIdx[kId].cpu().data[0]%prpSize)
                    fRsId = int((sortIdx[kId]/prpSize).cpu().data[0])
                    prpBoxArr = copy.deepcopy(prpList[bId][fRsId][prpRsId])
                    prpBoxArr.append(rsV)
                    prpBoxArr[2] = prpBoxArr[2]+ prpBoxArr[0]
                    prpBoxArr[3] = prpBoxArr[3]+ prpBoxArr[1]
                    prpBoxArr = np.array(prpBoxArr)
                    prpBoxArr = np.expand_dims(prpBoxArr, axis=0)
                    imgList[fRsId] = vis_detections(imgList[fRsId], prpBoxArr, \
                            thresh=-1, topK=1, color=0)
                    print(fRsId)
                    print(prpBoxArr)

                bbxGtIJ = copy.deepcopy(prpBox)
                bbxGtIJ[2] = bbxGtIJ[2]+bbxGtIJ[0]
                bbxGtIJ[3] = bbxGtIJ[3]+bbxGtIJ[1]
                bbxGtIJ.append(1)
                gtArr = np.array(bbxGtIJ)
                gtArr = np.expand_dims(gtArr, axis=0)
                im_show2 = vis_detections(img, gtArr, thresh=-1, topK=1, color=1)
                im_show2= putCapOnImage(im_show2, annDict['cap'][lbl])

                imNameRaw= os.path.basename(imFullPath).split('.')[0]
                makedirs_if_missing(fdPre)
                gtName = fdPre + '/' + vdName +'_'+ imNameRaw +'_'+str(fId)+'_'+str(pii)+'_gt.jpg'
                cv2.imwrite(gtName, im_show2)
                for i in range(frmSize):
                    detName = fdPre + '/'+vdName +'_' + imNameRaw +'_'+str(fId)+'_'+str(pii)+'_det' + '_' + str(i)+ '.jpg'
                    cv2.imwrite(detName, imgList[i])

