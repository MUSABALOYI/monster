import traceback

from chef import Node as CNode

from monster import util
from monster.nodes.node import Node
from monster.features import node_features
from monster.provisioners import provisioner as provisioners


class ChefNode(Node):
    """
    A chef entity
    Provides chef related server fuctions
    """
    def __init__(self, ip, user, password, os, product, environment,
                 deployment, name, provisioner, branch, status=None,
                 run_list=None):
        super(ChefNode, self).__init__(ip, user, password, os, product,
                                       environment, deployment, provisioner,
                                       status)
        self.name = name
        self.branch = branch
        self.run_list = run_list or []
        self.features = []

    def __str__(self):
        features = ", ".join(self.feature_names())
        node = ("Node - name:{0}, os:{1}, branch:{2}, ip:{3}, status:{4}\n\t\t"
                "Features: {5}").format(self.name, self.os_name, self.branch,
                                        self.ipaddress, self.status, features)
        return node

    def __getitem__(self, item):
        """
        Node has access to chef attributes
        """
        return CNode(self.name, api=self.environment.local_api)[item]

    def __setitem__(self, item, value):
        """
        Node can set chef attributes
        """
        util.logger.debug("setting {0} to {1} on {2}".format(item, value,
                                                             self.name))
        lnode = CNode(self.name, api=self.environment.local_api)
        lnode[item] = value
        self.save(lnode)

    def build(self):
        # clear run_list
        self.run_list = []
        node = CNode(self.name, self.environment.local_api)
        node.run_list = []
        node.save()
        super(ChefNode, self).build()

    def save_to_node(self):
        """
        Save deployment restore attributes to chef environment
        """
        features = [str(f).lower() for f in self.features]
        node = {'features': features,
                'status': self.status,
                'provisioner': self.provisioner.__class__.__name__.lower()}
        self['archive'] = node

    def apply_feature(self):
        """
        Runs chef client before apply features on node
        """
        self.status = "apply-feature"
        if not self.feature_in("chefserver"):
            self.run_chef_client()
        super(ChefNode, self).apply_feature()

    def save(self, chef_node=None):
        chef_node = chef_node or CNode(self.name, self.environment.local_api)
        chef_node.save(self.environment.local_api)
        if self.environment.remote_api:
            chef_node.save(self.environment.remote_api)

    def save_locally(self, chef_node=None):
        if self.environment.remote_api:
            chef_node = chef_node or CNode(self.name,
                                           self.environment.remote_api)
            chef_node.save(self.environment.local_api)

    def get_run_list(self):
        return CNode(self.name, self.environment.local_api).run_list

    def add_run_list_item(self, items):
        """
        Adds list of items to run_list
        """
        util.logger.debug("run_list:{0} add:{1}".format(self.run_list, items))
        self.run_list.extend(items)
        cnode = CNode(self.name, api=self.environment.local_api)
        cnode.run_list = self.run_list
        self.save(cnode)

    def add_features(self, features):
        """
        Adds a list of feature classes
        """
        util.logger.debug("node:{0} feature add:{1}".format(self.name,
                                                            features))
        classes = util.module_classes(node_features)
        for feature in features:
            feature_class = classes[feature](self)
            self.features.append(feature_class)

        # save features for restore
        self.save_to_node()

    @classmethod
    def from_chef_node(cls, node, os=None, product=None, environment=None,
                       deployment=None, provisioner=None, branch=None):
        """
        Restores node from chef node
        """
        ipaddress = node['ipaddress']
        user = node['current_user']
        password = node['password']
        name = node.name
        archive = node.get('archive', {})
        status = archive.get('status', "provisioning")
        if not provisioner:
            provisioner_name = archive.get('provisioner',
                                           "chefrazorprovisioner")
            classes = util.module_classes(provisioners)
            provisioner = classes[provisioner_name]()
        run_list = node.run_list
        crnode = cls(ipaddress, user, password, os, product, environment,
                     deployment, name, provisioner, branch, status=status,
                     run_list=run_list)
        try:
            crnode.add_features(archive.get('features', []))
        except:
            util.logger.error(traceback.print_exc())
            crnode.destroy()
            raise Exception("Node feature add fail{0}".format(str(crnode)))
        return crnode

    def run_chef_client(self, times=1):
        for _ in xrange(times):
            self.run_cmd("chef-client")
            self.save_locally()
