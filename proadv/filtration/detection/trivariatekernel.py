import numpy as np
from scipy import linalg
from scipy.stats._stats import gaussian_kernel_estimate as gke
from scipy.stats import gaussian_kde as kde

def _derivatives(data):

    dc = np.zeros_like(data)
    dc2 = np.zeros_like(data)

    for i in range(1, data.size - 1):
        dc[i] = (data[i + 1] - data[i - 1]) / 2

    for i in range(1, data.size - 1):
        dc2[i] = (dc[i + 1] - dc[i - 1]) / 2

    return dc, dc2


def _rotation(u1, w1):

    data_size = u1.size

    theta = np.arctan2((data_size * np.sum(u1 * w1) - np.sum(u1) * np.sum(w1)),
                       (data_size * np.sum(u1 * u1) - np.sum(u1) * np.sum(u1)))
    
    return theta


def _transform(x, y, theta):

    xt = x * np.cos(theta) + y * np.sin(theta)

    yt = -x * np.sin(theta) + y * np.cos(theta)

    return xt, yt


def _scaling(x, y, grid):
    xmin = x.min()
    xmax = x.max()
    ymin = y.min()
    ymax = y.max()
    return np.mgrid[xmin:xmax:grid * 1j, ymin:ymax:grid * 1j]


def _profile(meshgrid_x, meshgrid_y):
    return meshgrid_x[:, 0], meshgrid_y[0, :]


def _position(meshgrid_x, meshgrid_y, trans_x, trans_y):
    positions = np.vstack([meshgrid_x.ravel(), meshgrid_y.ravel()])
    
    values = np.vstack([trans_x, trans_y])

    return positions, values


def _factor(rows, cols):
    return np.power(cols, -1. / (rows + 4))


def _weight(cols):
    return np.ones(cols) / cols


def _cov(data, aweights):
    return np.atleast_2d(np.cov(data, rowvar=1, bias=False, aweights=aweights))


def _cholesky(data):
    return linalg.cholesky(data)


def _determination(data):
    return 2 * np.sum(np.log(np.diag(data * np.sqrt(np.pi * 2))))


def _covariance(data, rows, cols):
    factor = _factor(rows, cols)
    weight = _weight(cols)
    net = np.power(np.sum(weight ** 2), -1)
    factor = _factor(rows, net)
    cov = _cov(data, weight)
    sky = _cholesky(cov)
    covariance = cov * factor ** 2
    cholesky = sky * factor
    cholesky.dtype = np.float64
    log = _determination(cholesky)
    compute = {
        "factor": factor,
        "weight": weight,
        "net": net,
        "covariance": covariance,
        "cholesky": cholesky,
        "log": log
    }
    return compute


def _type(cov, scatt):
    data_type = np.common_type(cov, scatt)
    data_size = np.dtype(data_type).itemsize
    if data_size == 4:
        data_size = 'float'
    elif data_size == 8:
        data_size = 'double'
    elif data_size in (12, 16):
        data_size = 'long double'
    return data_type, data_size


def _density(values):
    dataset = np.atleast_2d(np.asarray(values))
    if dataset.size < 1:
        raise ValueError("Dataset should have more than one element.")
    rows, cols = dataset.shape
    if rows > cols:
        raise ValueError("Number of dimensions exceeds the number of samples.")
    evals = _covariance(dataset, rows, cols)
    return evals


def _estimation(kde, x):
    return np.reshape(kde, x.shape)


def _extraction(dataset, parameters, poses):
    scatt = np.atleast_2d(np.asarray(poses))
    data_type, data_mode = _type(parameters["covariance"], scatt)
    return dataset.T, parameters["weight"][:, None], poses.T, parameters["cholesky"].T, data_type, data_mode


def _evolve(dataset, poses, computations):
    dataset = _extraction(dataset, computations, poses)
    dens = gke[dataset[5]](
        dataset[0],
        dataset[1],
        dataset[2],
        dataset[3],
        dataset[4])
    return dens[:, 0]


def _peak(pdf):
    peak = pdf.max()
    up, wp = np.where(pdf == peak)[0][0], np.where(pdf == peak)[1][0]
    fu = pdf[:, wp]
    fw = pdf[up, :]
    return peak, up, wp, fu, fw


def _cutoff(dp, uf, c1, c2, f, Ip, ngrid):
    lf = f.size
    dk = np.append([0], np.diff(f)) * ngrid / dp
    for i in list(range(1, Ip))[::-1]:
        if f[i] / f[Ip] <= c1 and abs(dk[i]) <= c2:
            i1 = i
            break
        else:
            i1 = 1

    for i in range(Ip + 1, lf - 1):
        if f[i] / f[Ip] <= c1 and abs(dk[i]) <= c2:
            i2 = i
            break
        else:
            i2 = lf - 1
    ul = uf[i1]
    uu = uf[i2]
    return ul, uu