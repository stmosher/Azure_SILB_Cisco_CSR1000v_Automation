#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

Copyright (c) 2019 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.

"""
__author__ = "Steven Mosher <stmosher@cisco.com>"
__copyright__ = "Copyright (c) 2019 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.1"

import logging
from jinja2 import Template
import paramiko
import time
from config import Settings


class Router:
    """
    rtr.configure_router(rtr.render_config_from_template('templates/baseline.j2', variables_dict={'router_name': 'test123'}))
    """
    def __init__(self, public_ip, username, password, region, instance_type=None, max_bandwidth=1000):
        self.settings = Settings
        self.public_ip = public_ip
        self.username = username
        self.password = password
        self.region = region
        self.instance_type = instance_type
        self.max_bandwidth = max_bandwidth
        
    def register(self):
        if not self.set_license_info():
            return False
        if not self.render_smart_license_configure():
            return False
        if not self.render_smart_license_enable():
            return False
        if not self.configure_router(self.smart_license_configure_config):
            return False
        if not self.ensure_registered():
            return False
        if not self.configure_router(self.smart_license_enable_config):
            return False
        return True

    def deregister(self):
        logger = logging.getLogger(__name__)
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(self.public_ip,
                      username=self.username,
                      password=self.password,
                      timeout=15.0)
            ssh = c.invoke_shell()
            self.prompt(ssh)
            ssh.send('license smart deregister\n')
            self.prompt(ssh)
            ssh.send('wr mem\n')
            self.prompt(ssh)
            ssh.close()
            logger.info('Router %s successfully deregistered smart license', self.public_ip)
            return True
        except Exception as e:
            logger.error(e)
            return False

    def set_license_info(self):
        try:
            # sort all license dictionaries by bandwidth
            # pick the first license that is larger than the requested amount
            # if there isn't one then pick the last one
            self.license_token = False
            licenses = self.settings.licenses
            licenses.sort(key=lambda k: k['license_throughput'], reverse=False)
            for i in licenses:
                if int(self.max_bandwidth) <= i['license_throughput']:
                    self.license_token = i['license_token']
                    self.license_feature_set = i['license_feature_set']
                    self.license_throughput = i['license_throughput']
                    break
            if not self.license_token:
                self.license_token = licenses[-1]['license_token']
                self.license_feature_set = licenses[-1]['license_feature_set']
                self.license_throughput = licenses[-1]['license_throughput']
            return True
        except:
            return False

    def render_smart_license_configure(self):
        try:
            smart_license_configure_template = f"""
            ip name-server {self.settings.dns_server}
            ip http client source-interface GigabitEthernet1
            ip domain lookup source-interface GigabitEthernet1
            !
            call-home
              contact-email-addr {self.settings.email_address}
              profile CiscoTAC-1
                active
                destination transport-method http
                destination address http {self.settings.smart_licensing_server}
            !
            service call-home
            license smart enable
            !
            end
            !
            license smart register idtoken {self.license_token}

            """
            self.smart_license_configure_config = smart_license_configure_template.split('\n')
            return True
        except:
            return False

    def render_smart_license_enable(self):
        try:
            smart_license_enable_template = f"""
            license boot level {self.license_feature_set}
            platform hardware throughput level MB {str(self.license_throughput)}
            """
            self.smart_license_enable_config = smart_license_enable_template.split('\n')
            return True
        except:
            return False

    def configure_router(self, config_input):
        logger = logging.getLogger(__name__)
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(self.public_ip,
                      username=self.username,
                      password=self.password,
                      timeout=15.0)
            ssh = c.invoke_shell()
            self.prompt(ssh)
            ssh.send('config t\n')
            self.prompt(ssh)
            for line in config_input:
                ssh.send(line + '\n')
                self.prompt(ssh)
            ssh.send('end\n')
            self.prompt(ssh)
            ssh.send('wr mem\n')
            self.prompt(ssh)
            ssh.close()
            logger.info('Router %s successfully configured', self.public_ip)
            return True
        except Exception as e:
            logger.error(e)
            return False

    def ensure_registered(self):
        logger = logging.getLogger(__name__)
        counter = 0
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(self.public_ip,
                      username=self.username,
                      password=self.password,
                      timeout=15.0)
            ssh = c.invoke_shell()
            self.prompt(ssh)
            while counter != 4:
                ssh.send('show license summary\n')
                result = self.prompt(ssh)
                lines = result.splitlines()
                if 'Smart Licensing is ENABLED' in lines:
                    logger.info('Router %s smart licensing registered!', self.public_ip)
                    ssh.close()
                    return True
                time.sleep(2)
                counter += 1
            ssh.close()
            logger.warning('Router %s unable to register with smart licensing', self.public_ip)
            return False
        except Exception as e:
            logger.error(e)
            return False

    @staticmethod
    def prompt(chan):
        buff = ''
        while not buff.endswith('#'):
            resp = chan.recv(9999)
            resp1 = resp.decode('utf-8')
            buff += resp1
        return buff
    
    def check_responsive(self):
        logger = logging.getLogger(__name__)
        counter = 0
        while counter < 3:
            try:
                c = paramiko.SSHClient()
                c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                c.connect(self.public_ip,
                          username=self.username,
                          password=self.password,
                          timeout=15.0)
                ssh = c.invoke_shell()
                ssh.send('show version\n')
                self.prompt(ssh)
                ssh.close()
                return True
            except:
                if counter < 3:
                    time.sleep(1)
                    counter += 1
                else:
                    logger.warning('Exception driven Responsive test failed for {}'.format(self.public_ip))
                    return False
        logger.warning('Responsive test failed for {}'.format(self.public_ip))
        return False

    def initial_check_responsive(self):
        logger = logging.getLogger(__name__)
        counter = 0
        while counter < 90:
            try:
                print(str(counter))
                c = paramiko.SSHClient()
                c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                c.connect(self.public_ip,
                          username=self.username,
                          password=self.password,
                          timeout=5.0)
                ssh = c.invoke_shell()
                ssh.send('show version\n')
                self.prompt(ssh)
                ssh.close()
                return True
            except:
                if counter < 90:
                    time.sleep(5)
                    counter += 1
                else:
                    logger.warning('Exception driven Responsive test failed for {}'.format(self.public_ip))
                    return False
        logger.warning('Responsive test failed for {}'.format(self.public_ip))
        return False

    def render_config_from_template(self, template_name, variables_dict=None):
        settings = Settings()
        try:
            with open(template_name, 'r') as t:
                template_data = t.readlines()
            configuration = list()
            conf_vars_dict = vars(self)
            if variables_dict:
                conf_vars_dict.update(variables_dict)
            conf_vars_dict['settings'] = dict()
            conf_vars_dict['settings']['dmvpn_password'] = settings.dmvpn_password
            print(conf_vars_dict)

            for line in template_data:
                line = line.rstrip('\n')
                t = Template(line)
                new_line = t.render(conf_vars_dict)
                configuration.append(new_line)
            return configuration
        except Exception as e:
            print(e)
            return False


