import datetime
import sys
import shutil
import gc

from keras.callbacks import EarlyStopping, CSVLogger, ModelCheckpoint, LearningRateScheduler, TensorBoard

import model_structure
from load_data import data_generator, test_generator, get_test_true
from Param_DMVST_flow import *


def mkdir(path):
    folder = os.path.exists(path)
    if not folder:
        os.makedirs(path)


def get_model_structure(name):
    model = model_structure.get_model(name)
    model.summary()

    # model_json = model.to_json()
    # with open('model_data/structure/' + name + '.json', "w") as json_file:
    #     json_file.write(model_json)

    return model


def get_data(model_name, type):
    print('loading data...')

    all_data_len = 0
    for i in range(len(local_flow_in_lst_path)):
        data = np.load(local_flow_in_lst_path[i])
        all_data_len += data.shape[0]
    train_start, valid_start, test_start = \
        0, int(all_data_len * trainRatio * (1 - SPLIT)) - TIMESTEP, int(all_data_len * trainRatio) - TIMESTEP
    print('train len:', valid_start - train_start)
    print('valid len:', test_start - valid_start)
    print('test len:', all_data_len - test_start)

    trainData, validData, testData, trainTemporal, validTemporal, testTemporal = [], [], [], [], [], []
    data_len = 0
    for i in range(len(local_flow_in_lst_path)):
        if type == 'in':
            local_density_path = local_flow_in_lst_path[i]
            topo_density_path = topo_flow_in_path
        elif type == 'out':
            local_density_path = local_flow_out_lst_path[i]
            topo_density_path = topo_flow_out_path
        if model_name == 'density':
            region_window = np.load(local_density_path)
            topo_data = np.loadtxt(topo_density_path, skiprows=1, usecols=range(1, toponet_len + 1))
        temporal_data = np.loadtxt(temporal_lst_path[i], skiprows=1, delimiter=',')
        print('data set:', i)
        print('population data', region_window.shape)
        print('temporal data', temporal_data.shape)
        print('topo data', topo_data.shape)
        print('\n')
        data_len += region_window.shape[0]

        region_window = region_window / MAX_VALUE

        if data_len <= valid_start:
            trainData.append(region_window)
            trainTemporal.append(temporal_data)
        elif data_len <= test_start:
            trainData.append(region_window[:valid_start - data_len])
            trainTemporal.append(temporal_data[:valid_start - data_len])
            validData.append(region_window[valid_start - data_len:])
            validTemporal.append(temporal_data[valid_start - data_len:])
        else:
            validData.append(region_window[:test_start - data_len])
            validTemporal.append(temporal_data[:test_start - data_len])
            testData.append(region_window[test_start - data_len:])
            testTemporal.append(temporal_data[test_start - data_len:])

    print('train data', sum([len(x) for x in trainData]))
    print('valid data', sum([len(x) for x in validData]))
    print('test data', sum([len(x) for x in testData]))
    print('load finished')

    return trainData, validData, testData, trainTemporal, validTemporal, testTemporal, topo_data


def model_train(model_name, train_data, valid_data, trainTemporal, validTemporal, topo_data, type):
    # set callbacks
    csv_logger = CSVLogger(PATH + '/' + MODELNAME + '_' + type + '.log')
    checkpointer_path = PATH + '/' + MODELNAME + '_' + type + '.h5'
    checkpointer = ModelCheckpoint(filepath=checkpointer_path, verbose=1, save_best_only=True)
    early_stopping = EarlyStopping(monitor='val_loss', patience=10, verbose=1, mode='auto')
    LearnRate = LearningRateScheduler(lambda epoch: LR)

    # data generator
    train_generator = data_generator(train_data, trainTemporal, topo_data, BATCHSIZE, TIMESTEP, model_name)
    val_generator = data_generator(valid_data, validTemporal, topo_data, BATCHSIZE, TIMESTEP, model_name)
    sep = (sum([len(x) for x in train_data]) - TIMESTEP * len(train_data)) * train_data[0].shape[1] // BATCHSIZE
    val_sep = (sum([len(x) for x in valid_data]) - TIMESTEP * len(valid_data)) * valid_data[0].shape[1] // BATCHSIZE

    # train model
    model = get_model_structure(model_name)
    # model = multi_gpu_model(model, gpus=2)  # gpu parallel
    model.compile(loss=LOSS, optimizer=OPTIMIZER)
    model.fit_generator(train_generator, steps_per_epoch=sep, epochs=EPOCH,
                        validation_data=val_generator, validation_steps=val_sep,
                        callbacks=[csv_logger, checkpointer, LearnRate, early_stopping])

    # compute mse
    val_nolabel_generator = test_generator(valid_data, validTemporal, topo_data, BATCHSIZE, TIMESTEP)
    val_predY = model.predict_generator(val_nolabel_generator, steps=val_sep)
    valY = get_test_true(valid_data, TIMESTEP, model_name)
    # mse
    scaled_valY = np.reshape(valY, ((sum([len(x) for x in valid_data]) - TIMESTEP * len(valid_data)), HEIGHT, WIDTH))
    scaled_predValY = np.reshape(val_predY,
                                 ((sum([len(x) for x in valid_data]) - TIMESTEP * len(valid_data)), HEIGHT, WIDTH))
    print('val scale shape: ', scaled_predValY.shape)
    val_scale_MSE = np.mean((scaled_valY - scaled_predValY) ** 2)
    print("Model val scaled MSE", val_scale_MSE)
    # rescale mse
    val_rescale_MSE = val_scale_MSE * MAX_VALUE ** 2
    print("Model val rescaled MSE", val_rescale_MSE)

    # write record
    with open(PATH + '/' + MODELNAME + '_prediction_scores.txt', 'a') as wf:
        wf.write('train flow {} start time: {}\n'.format(type, StartTime))
        wf.write('train flow {} end time:   {}\n'.format(type, datetime.datetime.now().strftime('%Y%m%d_%H%M%S')))
        wf.write("Keras MSE on flow {} trainData, {}\n".format(type, val_scale_MSE))
        wf.write("Rescaled MSE on flow {} trainData, {}\n".format(type, val_rescale_MSE))
    return val_scale_MSE, val_rescale_MSE


def model_pred(model_name, test, testTemporal, topo_data, type):
    # test generator
    test_gene = test_generator(test, testTemporal, topo_data, BATCHSIZE, TIMESTEP)
    test_sep = (sum([len(x) for x in test]) - TIMESTEP * len(test)) * test[0].shape[1] // BATCHSIZE

    # get predict
    model = get_model_structure(model_name)
    # model = multi_gpu_model(model, gpus=2)  # gpu parallel
    model.compile(loss=LOSS, optimizer=OPTIMIZER)
    model.load_weights(PATH + '/' + MODELNAME + '_' + type + '.h5')
    predY = model.predict_generator(test_gene, steps=test_sep)

    # ground truth
    testY = get_test_true(test, TIMESTEP, model_name)

    # compute mse
    scaled_testY = np.reshape(testY, (sum([len(x) for x in test]) - TIMESTEP * len(test), HEIGHT, WIDTH))
    scaled_predTestY = np.reshape(predY, (sum([len(x) for x in test]) - TIMESTEP * len(test), HEIGHT, WIDTH))
    print('test scale shape: ', scaled_predTestY.shape)
    scale_MSE = np.mean((scaled_testY - scaled_predTestY) ** 2)
    print("Model scaled MSE", scale_MSE)

    rescale_MSE = scale_MSE * MAX_VALUE ** 2
    print("Model rescaled MSE", rescale_MSE)

    with open(PATH + '/' + MODELNAME + '_prediction_scores.txt', 'a') as wf:
        wf.write("Keras MSE on flow {} testData, {}\n".format(type, scale_MSE))
        wf.write("Rescaled MSE on flow {} testData, {}\n\n".format(type, rescale_MSE))

    return scale_MSE, rescale_MSE


################# Path Setting #######################
MODELNAME = 'DMVST'
KEYWORD = 'predflowio_' + MODELNAME + '_' + datetime.datetime.now().strftime("%y%m%d%H%M")
PATH = '../' + KEYWORD
###########################Reproducible#############################
import numpy as np
import random
from keras import backend as K
import os
import tensorflow as tf

np.random.seed(100)
random.seed(100)
os.environ['PYTHONHASHSEED'] = '0'  # necessary for py3

tf.set_random_seed(100)
session_conf = tf.ConfigProto(intra_op_parallelism_threads=1, inter_op_parallelism_threads=1)
session_conf.gpu_options.allow_growth = True
session_conf.gpu_options.per_process_gpu_memory_fraction = 0.45
session_conf.gpu_options.visible_device_list = '3'
sess = tf.Session(graph=tf.get_default_graph(), config=session_conf)
K.set_session(sess)
###################################################################

if __name__ == '__main__':

    mkdir(PATH)
    currentPython = sys.argv[0]
    shutil.copy2(currentPython, PATH)
    shutil.copy2('Param_DMVST_flow.py', PATH)
    shutil.copy2('model_structure.py', PATH)
    shutil.copy2('load_data.py', PATH)
    shutil.copy2('preprocess_flow.py', PATH)
    StartTime = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    choose = 0
    if choose == 0:
        # density
        model_name = 'density'

    print('#' * 50)
    print('start running at {}'.format(StartTime))
    print('model name: flow')
    print('#' * 50, '\n')

    val_sc, val_re, test_sc, test_re = [], [], [], []

    for type in ['in', 'out']:
        StartTime = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        train_data, valid_data, test_data, trainTemporal, validTemporal, testTemporal, topo_data = get_data(model_name,
                                                                                                            type)
        val_scale, val_rescale = model_train(model_name, train_data, valid_data, trainTemporal, validTemporal,
                                             topo_data, type)
        test_scale, test_rescale = model_pred(model_name, test_data, testTemporal, topo_data, type)
        val_sc.append(val_scale), val_re.append(val_rescale)
        test_sc.append(test_scale), test_re.append(test_rescale)
        del train_data, valid_data, test_data, trainTemporal, validTemporal, testTemporal, topo_data
        gc.collect()

    with open(PATH + '/' + MODELNAME + '_prediction_scores.txt', 'a') as wf:
        wf.write("\n\nKeras MSE on flow valData, {}\n".format(np.mean(val_sc)))
        wf.write("Keras MSE on flow testData, {}\n".format(np.mean(test_sc)))
        wf.write("Rescaled MSE on flow valData, {}\n".format(np.mean(val_re)))
        wf.write("Rescaled MSE on flow testData, {}\n".format(np.mean(test_re)))
