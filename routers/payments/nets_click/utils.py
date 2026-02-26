def split_0102(data):
    if data[:2] != '01':
        raise Exception("Invalid data")
    d01_len = int(data[2:5])
    d01 = data[5:5+d01_len]
    
    d02_ind = 5+d01_len
    if data[d02_ind:d02_ind+2] != '02':
        raise Exception("Invalid data")
    d02_len = int(data[d02_ind+2:d02_ind+5])
    d02 = data[d02_ind+5:]
    if len(d02) != d02_len:
        raise Exception("Invalid data")
    
    return d01, d02


def split_0205(data):
    print(data)
    if data[:2] != '02':
        raise Exception("Invalid data")
    d02_len = int(data[2:5])
    d02 = data[5:5+d02_len]
    
    d05_ind = 5+d02_len
    if data[d05_ind:d05_ind+2] != '05':
        raise Exception("Invalid data")
    d05_len = int(data[d05_ind+2:d05_ind+5])
    d05 = data[d05_ind+5:]
    if len(d05) != d05_len:
        raise Exception("Invalid data")
    
    return d02, d05
