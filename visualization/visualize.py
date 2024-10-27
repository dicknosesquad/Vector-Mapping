import json
import matplotlib.pyplot as plt

def visualize_map(data_file='data/data_center.json'):
    with open(data_file) as f:
        data = json.load(f)
    for rack in data['racks']:
        plt.scatter(rack['x'], rack['y'], c='blue')
        for drive in rack['drives']:
            plt.scatter(drive['x'], drive['y'], c='red')
    plt.show()
