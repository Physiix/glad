from collections import defaultdict
from datetime import datetime
from itertools import chain
import os.path
import sys

from glad.lang.common.loader import NullLoader
from glad.opener import URLOpener
from glad.util import api_name
import glad


if sys.version_info >= (3, 0):
    from urllib.parse import urlencode
else:
    from urllib import urlencode


HEADER_TEMPLATE = '''
    {apis_named} loader generated by glad {version} on {date}.

    Language/Generator: {language}
    Specification: {specification}
    APIs: {apis}
    Profile: {profile}
    Extensions:
        {extensions}
    Loader: {loader}

    Commandline:
        {commandline}
    Online:
        {online}
'''


class Generator(object):
    NAME = None
    NAME_LONG = None
    URL = 'http://glad.dav1d.de'

    def __init__(self, path, spec, api, extension_names=None, loader=None,
                 opener=None, header_template=HEADER_TEMPLATE):
        self.path = os.path.abspath(path)

        self.spec = spec
        for a in api:
            if a not in self.spec.features:
                raise ValueError(
                    'Unknown API "{0}" for specification "{1}"'
                    .format(a, self.spec.NAME)
                )
        self.api = api
        self.extension_names = extension_names

        self.has_loader = loader is None
        self.loader = loader
        if self.loader is None:
            self.loader = NullLoader

        self.opener = opener
        if self.opener is None:
            self.opener = URLOpener.default()

        self._header_template = header_template

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def generate(self):
        features = list()
        for api, version in self.api.items():
            features.extend(self.spec.features[api])

            if version is None:
                version = list(self.spec.features[api].keys())[-1]
                self.api[api] = version

            if version not in self.spec.features[api]:
                raise ValueError(
                    'Unknown version "{0}" for specification "{1}"'
                    .format(version, self.spec.NAME)
                )

        if self.extension_names is None:
           self. extension_names = list(chain.from_iterable(self.spec.extensions[a]
                                                            for a in self.api))

        e = list(chain.from_iterable(self.spec.extensions[a] for a in self.api))
        for ext in self.extension_names:
            if ext not in e:
                raise ValueError(
                    'Invalid extension "{0}" for specification "{1}"'
                    .format(ext, self.spec.NAME)
                )

        self.generate_header()

        types = [t for t in self.spec.types if t.api is None or t.api in self.api]
        self.generate_types(types)

        f = list()
        for api, version in self.api.items():
            f.extend([value for key, value in self.spec.features[api].items()
                        if key <= version])
        enums, functions = merge(f)
        self.generate_features(f)

        extensions = list()
        for api in self.api:
            extensions.extend(self.spec.extensions[api][ext]
                              for ext in self.extension_names if ext
                              in self.spec.extensions[api])
        self.generate_extensions(extensions, enums, functions)

        fs = defaultdict(list)
        es = defaultdict(list)
        for api, version in self.api.items():
            fs[api].extend(
                [value for key, value in
                 self.spec.features[api].items() if key <= version]
            )
            es[api].extend(self.spec.extensions[api][ext]
                           for ext in self.extension_names if ext
                           in self.spec.extensions[api])
        self.generate_loader(fs, es)

    @property
    def header(self):
        apis_named = ', '.join(sorted(set(api_name(api) for api in self.api)))
        date = datetime.now().strftime('%c')
        language = self.NAME_LONG
        specification = self.spec.NAME
        apis = ', '.join('{}={}'.format(api, '.'.join(map(str, version))) for api, version in self.api.items())
        profile = getattr(self.spec, 'profile', '-')
        extensions = ', '.join(self.extension_names)
        loader = 'Yes' if self.has_loader else 'No'
        online = self.online
        if len(online) > 2000:
            online = 'Too many extensions'

        return self._header_template.format(
            apis_named=apis_named,
            version=glad.__version__,
            date=date,
            language=language,
            specification=specification,
            apis=apis,
            profile=profile,
            extensions=extensions,
            loader=loader,
            commandline=self.commandline,
            online=online
        )

    @property
    def commandline(self):
        profile = getattr(self.spec, 'profile', None)
        if profile is not None:
            profile = '--profile="{}"'.format(profile)

        api = '--api="{}"'.format(','.join(
            '{}={}'.format(api, '.'.join(map(str, version))) for api, version in self.api.items())
        )
        generator = '--generator="{}"'.format(self.NAME)
        specification = '--spec="{}"'.format(self.spec.NAME)
        loader = '' if self.has_loader else '--no-loader'
        extensions = '--extensions="{}"'.format(','.join(self.extension_names))

        return ' '.join(filter(None, [
            profile, api, generator, specification, loader, extensions
        ]))

    @property
    def online(self):
        profile = getattr(self.spec, 'profile', None)
        if profile is not None:
            profile = ('profile', profile)

        api = [('api', s) for s in ('{}={}'.format(api, '.'.join(map(str, version))) for api, version in self.api.items())]
        generator = ('language', self.NAME)
        specification = ('specification', self.spec.NAME)
        loader = ('loader', 'on') if self.has_loader else None
        extensions = [('extensions', ext) for ext in self.extension_names]

        data = [profile, generator, specification, loader]
        data.extend(api)
        data.extend(extensions)
        data = list(filter(None, data))
        serialized = urlencode(data)

        return '{}/#{}'.format(self.URL, serialized)

    def generate_header(self):
        raise NotImplementedError

    def generate_loader(self, features, extensions):
        raise NotImplementedError

    def generate_types(self, types):
        raise NotImplementedError

    def generate_features(self, features):
        raise NotImplementedError

    def generate_extensions(self, extensions, enums, functions):
        raise NotImplementedError


def merge(features):
    enums = set()
    functions = set()

    for feature in features:
        enums |= set(feature.enums)
        functions |= set(feature.functions)

    return enums, functions
