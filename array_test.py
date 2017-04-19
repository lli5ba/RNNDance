__author__ = 'Leandra'
import numpy as np
if __name__ == "__main__":
    seq_feed = np.zeros((64,60,99))
    for i in range(60):
        seq_feed[:,i,:] = i
    for i in range(20):
        res = seq_feed[:, 3*i:3*i + 3, :]
        print (res.shape)
        x = res[0, 0, 0]
        y = res[0, 1, 0]
        z = res[0, 2, 0]
        print(x)
        print(y)
        print(z)