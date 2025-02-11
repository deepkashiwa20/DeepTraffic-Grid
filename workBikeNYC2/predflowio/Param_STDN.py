CITY = 'BikeNYC2'
START, END = '20160701', '20160829'
TIMESTEP = 6
trainRatio = 0.8  # train/test
SPLIT = 0.2  # train/val
MAX_VALUE = 299.0
freq = '30min'
INTERVAL = 30
HEIGHT = 10
WIDTH = 20
DAYTIMESTEP = int(24 * 60 / INTERVAL)
DATACHANNEL = 2
LR = 0.0001
BATCHSIZE = 200  # all:(T-TIMESTEP)*21*12, should be a divisor
EPOCH = 200
LOSS = 'mse'
OPTIMIZER = 'adam'

window_size = 9
short_term_lstm_seq_len = TIMESTEP
att_lstm_num = 3
long_term_lstm_seq_len = 3
hist_feature_daynum = 7
last_feature_num = 48
nbhd_size = 2  # for lstm features
cnn_flat_size = 128
cnn_filter = 32
empty_time = (hist_feature_daynum + att_lstm_num) * DAYTIMESTEP + long_term_lstm_seq_len
feature_vec_len = ((2 * nbhd_size + 1) * (2 * nbhd_size + 1) + last_feature_num + hist_feature_daynum) * DATACHANNEL

model_name = 'flowio'
dataPath = '../../{}/'.format(CITY)  # used by preprocess
# model_name = 'density'
# density_path = dataPath + 'densityK_{}_{}_{}_30min.npy'.format(CITY, START, END)  # used by preprocess
# save_path = dataPath + 'DMVST_density/'
# local_density_path = save_path + 'densityK_{}_{}_{}_30min_local.npy'.format(CITY, START, END)
flow_path = dataPath + 'flowioK_{}_{}_{}_{}min.npy'.format(CITY, START, END, INTERVAL)  # used by preprocess
save_path = dataPath + 'DMVST_flow/'
local_flow_in_path = save_path + 'flowioK_{}_{}_{}_{}min_local_in.npy'.format(CITY, START, END, INTERVAL)  # gene by preprocess, used by DMVST_Net
local_flow_out_path = save_path + 'flowioK_{}_{}_{}_{}min_local_out.npy'.format(CITY, START, END, INTERVAL)  # gene by preprocess, used by DMVST_Net

