# -*- coding:utf-8 -*-
# author:zhangwei

"""
   该脚本用于构建、训练、保存端到端声学模型；
   采用卷积神经网络进行训练；
"""

from general_function.file_wav import *
from general_function.file_dict import *
from general_function.gen_func import *
from readdata import DataSpeech

import numpy as np
import random

from keras.models import Model
from keras.layers import Input, Dense, Conv2D, MaxPooling2D
from keras.layers import Reshape, Lambda, Activation
from keras.layers import Dropout, BatchNormalization

from keras import backend as K
from keras.optimizers import Adam , SGD
from keras.utils import plot_model

class ModelSpeech():
    def __init__(self , datapath):
        MS_OUTPUT_SIZE = 3782
        self.MS_OUTPUT_SIZE = MS_OUTPUT_SIZE
        self.label_max_string_length = 64
        self.AUDIO_LENGTH = 2000
        self.FEATURE_LENGTH = 200
        self.datapath = datapath
        self._model , self.base_model = self.creat_model()

        self.slash = '/'
        if self.slash != self.datapath[-1]:
            self.datapath = self.datapath + self.slash
        pass

    def creat_model(self):
        input_data = Input(shape=[self.AUDIO_LENGTH, self.FEATURE_LENGTH, 1], name='Input')
        conv1 = Conv2D(filters=32, kernel_size=[3, 3], padding='same', activation='relu', use_bias=True, kernel_initializer='TruncatedNormal')(input_data)
        conv1 = BatchNormalization(epsilon=0.0002)(conv1)
        conv2 = Conv2D(filters=32, kernel_size=[3, 3], padding='same', activation='relu', use_bias=True, kernel_initializer='TruncatedNormal')(conv1)
        conv2 = BatchNormalization(epsilon=0.0002)(conv2)
        maxpool1 = MaxPooling2D(pool_size=[2, 2], strides=None, padding='valid')(conv2)

        conv3 = Conv2D(filters=64, kernel_size=[3, 3], padding='same', activation='relu', use_bias=True, kernel_initializer='TruncatedNormal')(maxpool1)
        conv3 = BatchNormalization(epsilon=0.0002)(conv3)
        conv4 = Conv2D(filters=64, kernel_size=[3, 3], padding='same', activation='relu', use_bias=True, kernel_initializer='TruncatedNormal')(conv3)
        conv4 = BatchNormalization(epsilon=0.0002)(conv4)
        maxpool2 = MaxPooling2D(pool_size=[2, 2], strides=None, padding='valid')(conv4)

        conv5 = Conv2D(filters=128, kernel_size=[3, 3], padding='same', activation='relu', use_bias=True, kernel_initializer='TruncatedNormal')(maxpool2)
        conv5 = BatchNormalization(epsilon=0.0002)(conv5)
        conv6 = Conv2D(filters=128, kernel_size=[3, 3], padding='same', activation='relu', use_bias=True, kernel_initializer='TruncatedNormal')(conv5)
        conv6 = BatchNormalization(epsilon=0.0002)(conv6)
        maxpool3 = MaxPooling2D(pool_size=[2, 2], strides=None, padding='valid')(conv6)

        reshape = Reshape([250, 3200])(maxpool3)
        dense2 = Dense(units=1024, activation='relu', use_bias=True, kernel_initializer='he_normal')(reshape)
        dense2 = BatchNormalization(epsilon=0.0002)(dense2)
        dense2 = Dropout(0.3)(dense2)

        dense3 = Dense(units=1024, activation='relu', use_bias=True, kernel_initializer='he_normal')(dense2)
        dense3 = BatchNormalization(epsilon=0.0002)(dense3)
        dense3 = Dropout(0.3)(dense3)

        dense4 = Dense(units=self.MS_OUTPUT_SIZE, use_bias=True, kernel_initializer='he_normal')(dense3)
        y_pred = Activation(activation='softmax', name='activation')(dense4)

        model_data = Model(inputs=input_data, outputs=y_pred)

        # model_data.summary()
        # plot_model(model_data , '1.png')

        labels = Input(shape=[self.label_max_string_length], name='labels', dtype='float32')
        input_length = Input(shape=[1], name='input_length', dtype='int64')
        label_length = Input(shape=[1], name='label_length', dtype='int64')
        loss_out = Lambda(self.ctc_lambda_func, output_shape=[1, ], name='ctc')([y_pred, labels, input_length, label_length])
        model = Model(inputs=[input_data, labels, input_length, label_length], outputs=loss_out)

        # model.summary()

        sgd = SGD(lr=0.0005, decay=1e-6, momentum=0.9, nesterov=True, clipnorm=5)
        adam = Adam(lr=0.0005, epsilon=1e-6)

        model.compile(optimizer=adam, loss={'ctc': lambda y_true, y_pred: y_pred})

        print('==========================模型创建成功=================================')
        return model, model_data
        pass

    def ctc_lambda_func(self, args):
        y_pred, labels, input_length, label_length = args
        y_pred = y_pred[:, :, :]
        return K.ctc_batch_cost(y_true=labels, y_pred=y_pred, input_length=input_length, label_length=label_length)

    def train_model(self , datapath , epoch=4 , save_step=2000 , batch_size=8):
        data = DataSpeech(datapath , 'train')
        num_data = data.get_data_num()
        yielddatas = data.data_generator(batch_size , self.AUDIO_LENGTH)
        for epoch in range(epoch):
            print('[*running] train epoch %d .' % epoch)
            n_step = 0
            while True:
                try:
                    print('[*message] epoch %d , Having training data %d+' % (epoch , n_step * save_step))
                    self._model.fit_generator(yielddatas , save_step)
                    n_step += 1
                except StopIteration:
                    print('======================Error StopIteration==============================')
                    break
                self.save_model(comments='_e_' + str(epoch) + '_step_' + str(n_step * save_step))
                self.test_model(datapath=self.datapath , str_dataset='train' , data_count=4)
                self.test_model(datapath=self.datapath , str_dataset='dev' , data_count=16)

    def load_model(self , filename='model_speech_e_0_step_16000.model'):
        self._model.load_weights(filename)
        self.base_model.load_weights(filename + '.base')

    def test_model(self , datapath='' , str_dataset='dev' , data_count=1):
        data = DataSpeech(self.datapath , str_dataset)
        num_data = data.get_data_num()
        # print num_data
        if data_count <=0 and data_count > num_data:
            data_count = num_data
        try:
            ran_num = random.randint(0 , num_data - 1)
            words_num = 0.
            word_error_num = 0.
            for i in range(data_count):
                data_input , data_labels = data.get_data((ran_num + i) % num_data)
                # print data_input
                num_bias = 0
                while data_input.shape[0] > self.AUDIO_LENGTH:
                    print('[*Error] data input is too long %d' % ((ran_num + i) % num_data))
                    num_bias += 1
                    data_input , data_labels = data.get_data((ran_num + i + num_bias) % num_data)

                pre = self.predict(data_input=data_input , input_len=data_input.shape[0] // 8)                               #卷积修改；
                words_n = data_labels.shape[0]
                words_num += words_n
                edit_distance = get_edit_distance(data_labels , pre)
                if edit_distance <= words_n:
                    word_error_num += edit_distance
                else:
                    word_error_num += words_n
            # print type(words_num)
            print('[*Test Result] Speech Recognition ' + str_dataset + ' set word error ratio : ' + str(word_error_num / words_num * 100) , '%')
        except StopIteration:
            print('=======================Error StopIteration 01======================')

    def save_model(self , filename='/home/zhangwei/speech_model/speech_model' , comments=''):
        self._model.save_weights(filename + comments + '.model')
        self.base_model.save_weights(filename + comments + '.model.base')
        f = open('steps24.txt' , 'w')
        f.write(filename + comments)
        f.close()

    def predict(self , data_input , input_len):
        batch_size = 1
        in_len = np.zeros((batch_size) , dtype=np.int32)
        in_len[0] = input_len
        x_in = np.zeros(shape=[batch_size , 2000 , self.FEATURE_LENGTH , 1] , dtype=np.float)
        for i in range(batch_size):
            x_in[i , 0 : len(data_input)] = data_input
        base_pred = self.base_model.predict(x=x_in)
        base_pred = base_pred[: , : , :]
        r = K.ctc_decode(base_pred , in_len , greedy=True , beam_width=100 , top_paths=1)
        r1 = K.get_value(r[0][0])
        r1 = r1[0]
        return r1

    def redognize_speech(self , wavsignal , fs):
        data_input = get_frequency_feature(wavsignal , fs)
        input_length = len(data_input)
        input_length = input_length // 8                                                         #卷积修改;
        data_input = np.array(data_input , dtype=np.float)
        data_input = data_input.reshape(data_input.shape[0] , data_input.shape[1] , 1)
        r1 = self.predict(data_input , input_length)
        # print r1
        list_symbol_dic = get_wav_list(self.datapath)
        r_str = []
        for i in r1:
            r_str.append(list_symbol_dic[i])
        return r_str

    def recognize_speech_fromfile(self , filename):
        wavsignal , fs = read_wav_data(filename)
        r = self.redognize_speech(wavsignal , fs)
        return r

if __name__ == '__main__':
    import tensorflow as tf
    # import tensorflow.compat.v1 as tf
    # tf.disable_v2_behavior()
    from keras.backend.tensorflow_backend import set_session
    config = tf.ConfigProto()
    config.gpu_options.per_process_gpu_memory_fraction = 0.9
    set_session(tf.Session(config=config))

    datapath = '.'
    ms = ModelSpeech(datapath)
    ms.train_model(datapath)
