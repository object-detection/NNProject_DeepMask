import datetime
import os
from Constants import mask_threshold
from FullNetGenerator import *
from ImageUtils import *
from keras.optimizers import SGD
from Losses import *
import math

sgd_lr = 0.001
sgd_decay = 0.00005
sgd_momentum = 0.9

batch_size = 32
last_i = 3
epochs = 50
epochs_to_backup_weights = 5

graph_arch_path = 'Resources/graph_architecture_with_transfer.json'
graph_weights_path = 'Resources/graph_weights_with_transfer.h5'
original_net_weights_path = 'Resources/vgg16_graph_weights.h5'
critical_loss = 500


def print_debug(str_to_print):
    print '%s: %s' % (datetime.datetime.now(), str_to_print)


def test_prediction(imgs, round_num, net, expected_result_arr, expected_masks, out):
    predictions = net.predict({'input': imgs})
    score_predictions = predictions['score_output'].flatten()
    print_debug('prediction %s' % score_predictions)
    evaluation = net.evaluate({'input': imgs, 'score_output': expected_result_arr, 'seg_output': expected_masks},
                              batch_size=1)
    print_debug('evaluation loss %s' % evaluation)
    out.write('%s,%s,%s\n' % (datetime.datetime.now(), evaluation, score_predictions))
    out.flush()

    for i in range(len(predictions['seg_output'])):
        mask = predictions['seg_output'][i]
        prediction_path = 'Predictions/round%d-pic%d.png' % (round_num, i)
        binarize_and_save_mask(mask, mask_threshold, prediction_path)

    return evaluation


def saved_net_exists():
    return os.path.isfile(graph_arch_path) and os.path.isfile(graph_weights_path)


def load_saved_net():
    print_debug('loading net...')
    net = model_from_json(open(graph_arch_path).read())
    net.load_weights(graph_weights_path)
    return net


def create_net():
    print_debug('creating net...')
    net_generator = FullNetGenerator(original_net_weights_path)
    net = net_generator.create_full_net()
    print_debug('net created:')
    print net.summary()
    return net


def compile_net(net):
    print_debug('compiling net...')
    sgd = SGD(lr=sgd_lr, decay=sgd_decay, momentum=sgd_momentum, nesterov=True)
    net.compile(optimizer=sgd, loss={'score_output': binary_regression_error,
                                     'seg_output': mask_binary_regression_error})
    return net


def save_net(net):
    print_debug('saving net...')
    json_string = net.to_json()
    open(graph_arch_path, 'w').write(json_string)
    net.save_weights(graph_weights_path)


def prepare_data():
    print_debug('preparing data...')
    img_paths = [
        'Predictions/49275-427041-0-0-1-1-im.png',
        'Predictions/131909-1304103-0-0-1-1-mir-im.png',
        'Predictions/155749-1441236-0-0-1-1-im.png',
        ]
    images = prepare_local_images(img_paths)

    expected_mask_paths = [str.replace(img_path, 'im', 'mask') for img_path in img_paths]
    expected_masks = prepare_expected_masks(expected_mask_paths)

    expected_results = [1, 1, 1]

    expected_result_arr = np.array([[res] for res in expected_results])

    return [images, expected_result_arr, expected_masks]


def main():
    losses = []
    out_path = 'Predictions/out-loss.csv'
    out = open(out_path, 'a')

    if saved_net_exists():
        graph = load_saved_net()
    else:
        graph = create_net()
        save_net(graph)

    compile_net(graph)  # current keras version cannot load compiled net with custom loss function
    [images, expected_result_arr, expected_masks] = prepare_data()

    print_debug('running net...')
    losses.append(test_prediction(images, last_i, graph, expected_result_arr, expected_masks, out))

    for i in range(last_i, epochs):
        print_debug('starting round %d:' % (i+1))
        graph.fit({'input': images, 'seg_output': expected_masks, 'score_output': expected_result_arr}, nb_epoch=1,
                  verbose=0)
        last_loss = test_prediction(images, i+1, graph, expected_result_arr, expected_masks, out)

        if math.isnan(last_loss) or math.isinf(last_loss) or last_loss >= critical_loss:
            print_debug("Loss %s too big- stopping" % losses[-1])
            break
        else:
            losses.append(last_loss)
            print_debug("Saving net weights for round %d" % (i+1))
            graph.save_weights('Predictions/net', overwrite=True)

        if i % epochs_to_backup_weights == 0:
            graph.save_weights('Predictions/net%d' % i)

    out.close()


if __name__ == "__main__":
    main()