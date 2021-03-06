"""
OpenStack deployments
"""

import types
import tmuxp
from monster import util


class Deployment(object):
    """Base for OpenStack deployments
    """

    def __init__(self, name, os_name, branch, provisioner, status, product,
                 clients=None):
        self.name = name
        self.os_name = os_name
        self.branch = branch
        self.features = []
        self.nodes = []
        self.status = status or "provisioning"
        self.provisioner = str(provisioner)
        self.product = product
        self.clients = clients

    def __repr__(self):
        """
        Print out current instance
        """

        outl = 'class: ' + self.__class__.__name__
        for attr in self.__dict__:
            if attr == 'features':
                features = "\tFeatures: {0}".format(
                    ", ".join((str(f) for f in self.features)))
            elif attr == 'nodes':
                nodes = "\tNodes: {0}".format(
                    "".join((str(n) for n in self.nodes)))
            elif isinstance(getattr(self, attr), types.NoneType):
                outl += '\n\t{0} : {1}'.format(attr, 'None')
            else:
                outl += '\n\t{0} : {1}'.format(attr, getattr(self, attr))

        return "\n".join([outl, features, nodes])

    def destroy(self):
        """
        Destroys an OpenStack deployment
        """

        self.status = "destroying"
        util.logger.info("Destroying deployment:{0}".format(self.name))
        for node in self.nodes:
            node.destroy()
        self.status = "destroyed"

    def update_environment(self):
        """
        Pre configures node for each feature
        """

        self.status = "loading environment"
        for feature in self.features:
            log = "Deployment feature: update environment: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.update_environment()
        util.logger.debug(self.environment)
        self.status = "environment ready"

    def pre_configure(self):
        """
        Pre configures node for each feature
        """

        self.status = "pre-configure"
        for feature in self.features:
            log = "Deployment feature: pre-configure: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.pre_configure()

    def build_nodes(self):
        """
        Builds each node
        """

        self.status = "building nodes"
        for node in self.nodes:
            node.build()
        self.status = "nodes built"

    def post_configure(self):
        """
        Post configures node for each feature
        """

        self.status = "post-configure"
        for feature in self.features:
            log = "Deployment feature: post-configure: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.post_configure()

    def build(self):
        """
        Runs build steps for node's features
        """

        util.logger.debug("Deployment step: update environment")
        self.update_environment()
        util.logger.debug("Deployment step: pre-configure")
        self.pre_configure()
        util.logger.debug("Deployment step: build nodes")
        self.build_nodes()
        util.logger.debug("Deployment step: post-configure")
        self.post_configure()
        self.status = "post-build"
        util.logger.info(self)

    def artifact(self):
        """
        Artifacts openstack and its dependant services for a deployment
        """

        self.log_path = "/var/log"
        self.etc_path = "/etc/"
        self.misc_path = "misc/"

        if self.deployment.os_name == 'precise':
            self.list_packages_cmd = ["dpkg -l"]
        else:
            self.list_packages_cmd = ["rpm -qa"]

        # Run each features archive
        for feature in self.features:
            feature.archive()

        # Run each nodes archive
        for node in self.nodes:
            node.archive()

    def search_role(self, feature):
        """
        Returns nodes the have the desired role
        :param feature: feature to be searched for
        :type feature: string
        :rtype: Iterator (Nodes)
        """

        return (node for node in
                self.nodes if feature in
                (str(f).lower() for f in node.features))

    def feature_in(self, feature):
        """
        Boolean function to determine if a feature exists in deployment
        :param feature: feature to be searched for
        :type feature: string
        :rtype: Boolean
        """

        if feature in (feature.__class__.__name__.lower()
                       for feature in self.features):
            return True
        return False

    def tmux(self):
        """
        Creates an new tmux session with an window for each node
        """

        server = tmuxp.Server()
        session = server.new_session(session_name=self.name)
        cmd = ("sshpass -p {1} ssh -o UserKnownHostsFile=/dev/null "
               "-o StrictHostKeyChecking=no -o LogLevel=quiet -l root {0}")
        for node in self.nodes:
            name = node.name[len(self.name) + 1:]
            window = session.new_window(window_name=name)
            pane = window.panes[0]
            pane.send_keys(cmd.format(node.ipaddress, node.password))

    def feature_names(self):
        """
        Returns list features as strings
        :rtype: list (string)
        """

        return [feature.__class__.__name__.lower() for feature in
                self.features]
