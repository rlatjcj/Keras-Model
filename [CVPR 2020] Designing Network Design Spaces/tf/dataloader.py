import os
import sys
import numpy as np
import pandas as pd
import tensorflow as tf

AUTO = tf.data.experimental.AUTOTUNE

mean_std = {
    'cub': [[0.48552202, 0.49934904, 0.43224954], 
            [0.18172876, 0.18109447, 0.19272076]],
    'cifar100': [[0.50707516, 0.48654887, 0.44091784], 
                 [0.20079844, 0.19834627, 0.20219835]],
}

def set_dataset(args):
    if 'cifar' in  args.dataset:
        def unpickle(file):
            import pickle
            with open(file, 'rb') as fo:
                dict = pickle.load(fo, encoding='bytes')
            return dict

        b_trainset = unpickle(os.path.join(args.data_path, 'train'))
        b_valset = unpickle(os.path.join(args.data_path, 'test'))
        # split = .2
        trainset_temp = {}
        valset_temp = {}
        for i, l in enumerate(b_trainset[b'fine_labels']):
            if not l in trainset_temp.keys():
                temp = np.dstack((b_trainset[b'data'][i][:1024].reshape((32,32)),
                                b_trainset[b'data'][i][1024:2048].reshape((32,32)),
                                b_trainset[b'data'][i][2048:].reshape((32,32))))
                trainset_temp[l] = temp[np.newaxis,...]
            else:
                temp = np.dstack((b_trainset[b'data'][i][:1024].reshape((32,32)),
                                b_trainset[b'data'][i][1024:2048].reshape((32,32)),
                                b_trainset[b'data'][i][2048:].reshape((32,32))))
                trainset_temp[l] = np.append(trainset_temp[l], temp[np.newaxis,...], axis=0)
                
        for i, l in enumerate(b_valset[b'fine_labels']):
            if not l in valset_temp.keys():
                temp = np.dstack((b_valset[b'data'][i][:1024].reshape((32,32)),
                                b_valset[b'data'][i][1024:2048].reshape((32,32)),
                                b_valset[b'data'][i][2048:].reshape((32,32))))
                valset_temp[l] = temp[np.newaxis,...]
            else:
                temp = np.dstack((b_valset[b'data'][i][:1024].reshape((32,32)),
                                b_valset[b'data'][i][1024:2048].reshape((32,32)),
                                b_valset[b'data'][i][2048:].reshape((32,32))))
                valset_temp[l] = np.append(valset_temp[l], temp[np.newaxis,...], axis=0)
                
        trainset = []
        valset = []
        for k, v in trainset_temp.items():
            for vv in v:
                trainset.append([vv, k])
                
        for k, v in valset_temp.items():
            for vv in v:
                valset.append([vv, k])
    else:
        trainset = pd.read_csv(
            os.path.join(
                args.data_path, '{}_trainset.csv'.format(args.dataset)
            )).values.tolist()
        valset = pd.read_csv(
            os.path.join(
                args.data_path, '{}_valset.csv'.format(args.dataset)
            )).values.tolist()

    return np.array(trainset, dtype='object'), np.array(valset, dtype='object')

#############################################################################
def fetch_dataset(path, y):
    x = tf.io.read_file(path)
    return tf.data.Dataset.from_tensors((x, y))

def dataloader(args, datalist, mode, batch_size, shuffle=True):
    '''dataloader for cross-entropy loss
    '''
    sys.path.append(args.baseline_path)
    from generator.augment import SimAugment
    
    def augmentation(img, label, shape):
        if args.augment == 'sim':
            augment = SimAugment(args, mode)

        for f in augment.augment_list:
            if 'crop' in f.__name__:
                img = f(img, shape)
            else:
                img = f(img)
        
        # one-hot encodding
        label = tf.one_hot(label, args.classes)
        return img, label

    def preprocess_image(img, label):
        if 'cifar' in args.dataset:
            shape = (32, 32, 3)
        else:
            shape = tf.image.extract_jpeg_shape(img)
            img = tf.io.decode_jpeg(img, channels=3)
        img, label = augmentation(img, label, shape)
        return (img, label)

    imglist, labellist = datalist[:,0].tolist(), datalist[:,1].tolist()
    if 'cifar' not in args.dataset:
        imglist = [os.path.join(args.data_path, i) for i in imglist]

    dataset = tf.data.Dataset.from_tensor_slices((imglist, labellist))
    dataset = dataset.repeat()
    if shuffle:
        dataset = dataset.shuffle(len(datalist))

    if 'cifar' not in args.dataset:
        dataset = dataset.interleave(fetch_dataset, num_parallel_calls=AUTO)
    dataset = dataset.map(preprocess_image, num_parallel_calls=AUTO)
    dataset = dataset.batch(batch_size)
    dataset = dataset.prefetch(AUTO)
    return dataset