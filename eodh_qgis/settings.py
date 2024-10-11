from qgis.PyQt import QtCore


class Settings:

    def __init__(self):
        self.group = "/eodh"
        self.data = {
            "auth_config": "",
            "check_update": False,
        }
        self.load_all()

    def load(self, key):
        qs = QtCore.QSettings()
        qs.beginGroup(self.group)
        value = qs.value(key)
        qs.endGroup()
        if value:
            self.data[key] = value

    def save(self, key, value):
        qs = QtCore.QSettings()
        qs.beginGroup(self.group)
        qs.setValue(key, value)
        qs.endGroup()

        self.load_all()

    def load_all(self):
        for k in self.data:
            self.load(k)
