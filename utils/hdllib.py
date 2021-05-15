#! /usr/bin/env python

"""Handle Management System client library.

This module implements the low-level client library for CNRI's Handle
Management System.  For general info about handles, see
http://www.handle.net/.  This module was built using the Handle
Resolution Protocol Specification at
http://www.handle.net/docs/client_spec.html, and inspection of (an
earlier version of) the client library sources.

Classes:

- Error -- exception for error conditions specific to this module 
- PacketPacker -- helper for packet packing
- PacketUnpacker -- helper for packet unpacking
- SessionTag -- helper for session tag management
- HashTable -- hash table

TO DO, doubts, questions:

XXX Constants should only have a prefix 'HP_' or 'HDL_' when their
    name occurs in the spec.  I've tried to fix this but may have
    missed some cases.

XXX Should break up get_data in send_request and poll_request.

XXX When retrying, should we generate a new tag or reuse the old one?
I think yes, but this means repacking the request.

"""

# XXX Charles says:
# 
# NOTE: The global handle system is considered handle system of last
# resort.  Therefore, the process is to obtain "homed" service
# information (ie. hash table) and use this information to return the
# data. If handle is not found, then query the global handle
# system. If the "homed" service information is the global handle
# system. The final query is not required.
# 
# There is not option for Authenticated queries. This is a query
# option. If the functions use mirroring handle servers to obtain
# information, then HDL_AUTHENTICATE query flag should be an
# option. If HDL_AUTHENTICATE query option is set, the primary servers
# is to be used to query for the handle.
# 
# I also noticed, that there is no retry mechanism. This would be very
# helpful for dropped packets, etc...
# 
# [Guido responds: yes there is!  If get_data() doesn't get a response
# in 5 seconds (changeable by the interval argument) it resends the
# request.]
# 
# I didn't see a caching of authority handles and/or service handles,
# this would be a tremendous increase for handle resolution.

import whrandom
import md5
import os
import select
import socket
import string
import time
import xdrlib

DEBUG = 0                               # Default debugging flag


# Internal constants
# XXX These need reorganizing
HANDLE_SERVICE_ID = 'HDL' + 13*' ' # Yes the spaces are important
HASH_TABLE_FILE_FALLBACK = 'hdl_hash.tbl'
DEFAULT_GLOBAL_SERVER = "hs.handle.net"
# XXX It is not guaranteed that IP addresses listed here will be the
# XXX global servers (says Charles)
DEFAULT_SERVERS = ['132.151.1.155',
                   '198.32.1.37',
                   '132.151.1.159',
                   '198.32.1.73']
DEFAULT_NUM_OF_BITS = 2
DEFAULT_HASH_FILE = '/usr/local/etc/hdl_hash.tbl'
DEFAULT_UDP_PORT = 2222
DEFAULT_TCP_PORT = 2222
DEFAULT_ADMIN_PORT = 80                 # Admin protocol uses HTTP now
FILE_NAME_LENGTH = 128
HOST_NAME_LENGTH = 64
MAX_BODY_LENGTH = 1024
UDP = 0
TCP = 1
PROTOCOL = 1
NO_CONFIG = -1
CONFIG = -2
FIRST_SCAN_OF_CONFIG = -3
SUCCESS = 1
FAILURE = -1



# Flag bits
HDL_NONMUTABLE = 0                      # LSB (0th bit)
HDL_DISABLED = 1                        # (1st bit)
flags_map = {0: 'HDL_NONMUTABLE', 1: 'HDL_DISABLED'}

# Handle protocol miscellaneous constants
HP_VERSION = 1                          # Handle protocol version

# Handle protocol lengths
HP_HEADER_LENGTH = 28                   # Packet header length
HP_MAX_COMMAND_SIZE = 512               # Max command packet length
HP_MAX_DATA_VALUE_LENGTH = 128
HP_HASH_HEADER_SIZE = 36

# Handle protocol commands (packet types)
HP_QUERY = 0
HP_QUERY_RESPONSE = 1
HP_HASH_REQUEST = 2
HP_HASH_RESPONSE = 3


# Handle data types
data_types = """
HDL_TYPE_NULL = -1                      # Indicates End of Type List
HDL_TYPE_URL = 0                        # Uniform Resource Locator
HDL_TYPE_EMAIL_RFC822 = 1               # E-Mail Address Defined In RFC822
HDL_TYPE_EMAIL_X400 = 2                 # E-Mail Address Defined By CCITT
HDL_TYPE_X500_DN = 3                    # Distinguished Name Defined By CCITT
HDL_TYPE_INET_HOST = 4                  # Internet host name or IP address
HDL_TYPE_INET_SERVICE = 5               # "hostname":"tcp"|"udp":"port"
HDL_TYPE_CONTACT_INFO = 6               # Same Syntax As EMAIL_RFC822
HDL_TYPE_DLS = 7                        # To be determined
HDL_TYPE_CACHE_PERIOD = 8               # Default caching period timeout
HDL_TYPE_HANDLE_TYPE = 9                # For Handle Service internal use
HDL_TYPE_SERVICE_HANDLE = 10            # Handle containing hash table info
HDL_TYPE_SERVICE_POINTER  = 11          # Service's hash table info
HDL_TYPE_URN = 12                       # Universal Resource Name
HDL_TYPE_TRANS_ID = 13                  # Transaction Identifier
# Non-registered types are > 65535
"""

# Put data_types mappings into the module's dictionary, and into the
# data_map dictionary.  Also create an inverted mapping.
exec data_types
data_map = {}
exec data_types in data_map
for key, value in data_map.items():
    if key != '__builtins__':
        data_map[value] = key



# Handle protocol error codes
error_codes = """
HP_OK = 0
HP_PARSING_FAILURE = 1
HP_VERSION_MISMATCH = 2
HP_ACCESS_TEMPORARILY_DENIED = 3
HP_NOT_RESPONSIBLE_FOR_HANDLE = 4
HP_HANDLE_NOT_FOUND = 5
HP_FORWARDED = 6
HP_INTERNAL_ERROR = 7
HP_TYPES_NOT_FOUND = 8
HP_REQUEST_TIMED_OUT = 9
HP_HANDLE_DOES_NOT_EXIST = 10
HP_FORWARD_ERROR = 11
"""

# See data_types comment above
exec error_codes
error_map = {}
exec error_codes in error_map
for key, value in error_map.items():
    if key != '__builtins__':
        error_map[value] = key

# Error code set by the parser
HDL_ERR_INTERNAL_ERROR = HP_INTERNAL_ERROR


# error class for this module
class Error:
    """Exception class for module hdllib."""
    def __init__(self, msg, err=None, info=None):
        self.msg = msg                  # Error message (string) or None
        self.err = err                  # Error code (int) or None
        self.info = info                # Additional info or None
    def __repr__(self):
        msg = "Error(%s" % `self.msg`
        if self.err is not None:
            msg = msg + ", %s" % `self.err`
        if self.info is not None:
            msg = msg + ", %s" % `self.info`
        msg = msg + ")"
        return msg
    def __str__(self):
        msg = self.msg or ""
        if self.err is not None:
            msg = msg + " (err=%s)" % str(self.err)
        if self.info is not None:
            msg = msg + " (info=%s)" % str(self.info)
        return msg



class PacketPacker:
    """Helper class to pack packets."""
    def __init__(self):
        self.p = xdrlib.Packer()

    def pack_header(self, tag=0, command=HP_QUERY, err=0, sequence=1,
                   total=1, version=HP_VERSION):
        """Pack the packet header (except the body length).

        The argument order differs from the order in the
        packet header so we can use defaults for most fields.

        """
        self.p.pack_uint(version)
        self.p.pack_uint(tag)
        self.p.pack_uint(command)
        self.p.pack_uint(sequence)
        self.p.pack_uint(total)
        self.p.pack_int(err)

    def pack_body(self, hdl, flags = [], types = [], replyport = 0,
                  replyaddr = '\0\0\0\0'):
        """Pack the packet body (preceded by its length)."""

        # Build the body first, so we can include its length
        # in the header
        p = xdrlib.Packer()
        p.pack_string(hdl)
        p.pack_uint(len(flags))
        for flag in flags:
            p.pack_uint(flag)
            p.pack_opaque(chr(1))
        p.pack_uint(len(types)) 
        for type in types:
            p.pack_uint(type)
        p.pack_uint(replyport)
        p.pack_opaque(replyaddr)

        body = p.get_buffer()

        self.p.pack_string(body)

    def get_buffer(self):
        return self.p.get_buffer()



class PacketUnpacker:
    """Helper class to unpack packets."""

    def __init__(self, data, debug=0):
        # Set the debug ivar and call the init stuff
        # needed by xdrlib.Unpacker.
        self.debug = debug
        self.u = xdrlib.Unpacker(data)
        
    def buf(self):
        try:
            return self.u.get_buffer()
        except AttributeError:
            # TBD: digusting hack made necessary by a missing
            # interface in xdrlib.Unpacker to get either the buffer or
            # the length of the remaining buffer.  this requires
            # knowledge of Python 1.4's name munging scheme so we can
            # peek at this object's private attribute.  This will be
            # fixed in Python 1.5.
            return self.u._Unpacker__buf

    def unpack_header(self):
        """Unpack a packet header (except the body length).

        The argument order corresponds to the arguments to
        packheader().

        """
        version = self.u.unpack_uint()
        tag = self.u.unpack_uint()
        command = self.u.unpack_uint()
        sequence = self.u.unpack_uint()
        total = self.u.unpack_uint()
        err = self.u.unpack_int()

        return (tag, command, err, sequence, total, version)

    def check_body_length(self):
        """Check that the body length matches what the header says.

        Set self.total_length.  If it doesn't, raise Error.

        """
        self.length_from_header = self.u.unpack_uint()
        if len(self.buf()) - self.u.get_position() != self.length_from_header:
            print "length according to header:",
            print self.length_from_header,
            print "actual length:",
            print len(buf) - self.u.get_position()
            raise Error("body length mismatch")

    def unpack_item_array(self):
        """Unpack an array of (type, value) pairs."""
        nopts = self.u.unpack_uint()
        opts = []
        for i in range(nopts):
            opt = self.u.unpack_uint()
            val = self.u.unpack_opaque()
            opts.append((opt, val))
        return opts
        
    def unpack_item_array_cont_chk(self, start):
        """Unpack an array of (type, value) pairs.

        Check to see if there is a continuation
        for this packet or if this *is* a continuation
        packet itself.

        """
        nopts = self.u.unpack_uint()
        if self.debug: print 'nopts=' + str(nopts)
        opts = []
        for i in range(nopts):
            opt = self.u.unpack_uint()
            if self.debug: print 'type=' + str(opt)
            #
            # Unpack the length value to determine if we have
            # a continuation packet.
            #
            length_from_body = self.u.unpack_int()
            if self.debug: print 'length from body=' + str(length_from_body)
            if length_from_body == 0:
                raise Error("Invalid zero packet length")
            #
            # If length_from_body < 0 , we've found a continuation
            # packet.  Pull off an additional field containing the
            # beginning offset in the buffer.
            #
            if length_from_body < 0:
                total_length = length_from_body * -1
                offset = self.u.unpack_uint()
                if self.debug: print 'Continuation packet'
                if offset < 0 or offset > total_length:
                    error = 'Bad offset in UDP body: ' + str(offset)
                    raise Error(error)
                max_length_from_total = total_length - offset
                max_length_from_size = len(self.buf()) \
                                       - self.u.get_position() - 16
                self.value_length = min(max_length_from_total,
                                        max_length_from_size)
                # Change opt to be negative flagging this as a continuation 
                opt = opt * -1

            else:
                # Normal packet, but it may be the start of a continuation
                if self.debug: print 'Normal Packet'
                total_length = self.value_length = length_from_body
                if self.debug: print "length from body =", length_from_body
                if nopts == 1:
                    max_value_length = len(self.buf()) \
                                       - self.u.get_position() - 16
                    if self.value_length > max_value_length:
                        if self.debug:
                            print 'Start of a continuation:',
                            print "max value length =", max_value_length
                        self.value_length = max_value_length
                #
                # Finally get the value
                if self.debug: print 'Getting data segment of ' \
                   + str(self.value_length) + ' bytes'
            value = self.u.unpack_fstring(self.value_length)
            if self.debug: print "Got", len(value), "bytes:", `value`
            opts.append((opt, value))
        return opts

    def set_debug(self):
        """Increment the debug ivar."""
        self.debug = self.debug + 1
        
    def unpack_request_body(self):
        """Unpack a request body (preceded by its length)."""

        self.check_body_length()

        hdl = self.u.unpack_string()

        options = self.u.unpack_item_array()

        ntypes = self.u.unpack_uint()
        types = []
        for i in range(ntypes):
            types.append(self.u.unpack_uint())

        replyport = self.u.unpack_uint()
        replyaddr = self.u.unpack_opaque()

        return (hdl, options, types, replyport, replyaddr)

    def unpack_reply_body(self):
        """Unpack a reply body (preceded by its length).

        Make sure the checksum is correct, else raise Error.

        """

        self.check_body_length()

        start = self.u.get_position()

        flags = self.u.unpack_opaque()
        
        items = self.unpack_item_array_cont_chk(start)

        checksum = self.u.unpack_fopaque(16)
        digest = md5.new(self.buf()[start:-16]).digest()

        if digest != checksum:
            raise Error("body checksum mismatch")
        return flags, items

    def unpack_error_body(self, err):
        """Unpack an error reply body according to the error code."""

        # XXX It would be convenient if the error code was saved as an
        # XXX ivar by unpack_header().

        self.check_body_length()

        if err == HP_NOT_RESPONSIBLE_FOR_HANDLE:
            server = self.u.unpack_string()
            udpport = self.u.unpack_int()
            tcpport = self.u.unpack_int()
            return (server, udpport, tcpport)
        elif err == HP_FORWARD_ERROR:
            return self.u.unpack_string()
        elif err == HP_VERSION_MISMATCH:
            return self.u.unpack_int()
        elif err == HP_ACCESS_TEMPORARILY_DENIED:
            return self.u.unpack_string()
        elif err == HP_PARSING_FAILURE:
            return self.u.unpack_string()
        else:
            # According to the spec, the other errors have no other
            # information associated with them.
            return None


class SessionTag:
    """Session tag.  See client library equivalent in
    create_tag.c: create_session_tag().

    Methods:

    session_tag() -- get next session tag

    XXX Why does it have to be a class anyway?

    """
    def session_tag(self):
        """Implemented as in create_session_tag()."""
        return whrandom.randint(0, 32767)



class HashTable:
    """Hash table.

    Public methods:

    - __init__([filename, [debug, [server, [data]]]]) -- constructor
    - set_debuglevel(debug) -- set debug level
    - hash_handle(hdl) -- hash a handle to handle server info
    - get_data(hdl, [types, [flags, [timeout, [interval]]]]]) --
      resolve a handle

    """ 
    def __init__(self, filename=None, debug=None, server=None, data=None):
        """Hash table constructor.

        If the optional data argument is given, filename and server
        are ignored, and the hash table is parsed directly from the
        data.

        Otherwise, If the optional server argument is given, filename
        is ignored, and a single bucket hash table is constructed
        using the default port and the given server.

        Otherwise, if a filename is give, read the hash table from
        that file.

        If neither filename nor server nor data are given, we try to
        load a hash table from the default location or from the
        fallback location, and if both fail, we construct one using
        hardcoded defaults.

        XXX This has only been tested with the default hash table at
        "ftp://cnri.reston.va.us/handles/client_library/hdl_hash.tbl;type=i"
        which (at the time of writing) has schema version 1.

        Exceptions:

        - Error
        - IOError
        - EOFError
        - whatever xdrlib raises besides EOFError

        """

        if debug is None: debug = DEBUG
        self.debug = debug

        self.tag = SessionTag()

        self.bucket_cache = {}

        if data:
            self._parse_hash_table(data)
        elif server:
            self._set_hardcoded_hash_table(server)
        elif filename:
            self._read_hash_table(filename)
        else:
            for fn in (DEFAULT_HASH_FILE, HASH_TABLE_FILE_FALLBACK):
                try:
                    self._read_hash_table(fn)
                except (IOError, Error), msg:
                    if self.debug:
                        print "Error for %s: %s" % (`fn`, str(msg))
                else:
                    break
            else:
                self._set_hardcoded_hash_table()


    def _set_hardcoded_hash_table(self, server=None):
        """Construct a hardcoded hash table -- internal.

        If the server argument is given, construct a single bucket
        from it using the default ports.  If the server argument is
        absent, construct a number of buckets using the default ports
        and the list of default servers.

        """
        if self.debug:
            if server:
                print "Constructing hardcoded hash table using", server
            else:
                print "Constructing hardcoded fallback hash table"
        if server:
            self.num_of_bits = 0
        else:
            self.num_of_bits = DEFAULT_NUM_OF_BITS
        up = DEFAULT_UDP_PORT
        tp = DEFAULT_TCP_PORT
        ap = DEFAULT_ADMIN_PORT
        for i in range(1<<self.num_of_bits):
            s = server or DEFAULT_SERVERS[i]
            if self.debug and not server:
                print 'Bucket', i, 'uses server', s
            self.bucket_cache[i] = (0, 0, s, up, tp, ap, -1)


    def _read_hash_table(self, filename):
        """Read the hash table from a given filename -- internal.

        Raise IOError if the file can't be opened.  After that, all
        its data is read and self._parse_hash_table() called.

        """
        if self.debug: print "Opening hash table:", `filename`
        fp = open(filename, 'rb')
        data = fp.read()
        fp.close()
        self._parse_hash_table(data)


    def _parse_hash_table(self, data):
        """Parse the hash table from given data -- internal.

        Raise Error if the MD5 checksum is invalid.  Raise EOFError
        if xdrlib finds a problem.

        If the data is valid, set a bunch of ivars to info read from
        the hash table header.  Note that the entire hash table is
        parsed here -- this simplifies the logic of hash_handle().

        """

        # XXX Charles says:
        # In the _parse_hash_table function, only the primary servers
        # are placed in the bucket cache. Therefore, the library does
        # not take advantage of mirroring handle servers.

        # Verify the checksum before proceeding
        checksum = data[:16]
        data = data[16:]
        if md5.new(data).digest() != checksum:
            raise Error("checksum error for hash table")

        # Read and decode header
        u = xdrlib.Unpacker(data[:4])
        self.schema_version = u.unpack_int()
        # The header_length field is not present if schema version < 2
        if self.schema_version < 2:
            if self.debug: print "Old hash table detected, version: %d" \
               % self.schema_version
            self.header_length = HP_HASH_HEADER_SIZE
            restofheader = data[4:self.header_length]
        else:
            u = xdrlib.Unpacker(data[4:8])
            self.header_length = u.unpack_int()
            restofheader = data[8:self.header_length]
        u = xdrlib.Unpacker(restofheader)
        self.data_version = u.unpack_int()
        self.num_of_bits = u.unpack_int()
        self.max_slot_size = u.unpack_int()
        self.max_address_length = u.unpack_int()
        self.unique_id = u.unpack_fopaque(16)

        if self.debug:
            print '*'*20
            print "Hash table file header:"
            print "Schema version:", self.schema_version
            print "header length: ", self.header_length
            print "data version:  ", self.data_version
            print "num_of_bits:   ", self.num_of_bits
            print "max slot size: ", self.max_slot_size
            print "max IP addr sz:", self.max_address_length
            print "unique ID:     ", hexstr(self.unique_id)
            print '*'*20

        # Parse the buckets
        for i in range(1<<self.num_of_bits):
            lo = self.header_length + i*self.max_slot_size
            hi = lo + self.max_slot_size
            bucketdata = data[lo:hi]
            self._parse_bucket(i, bucketdata)


    def _parse_bucket(self, index, data):
        """Parse one hash bucket and store it in the bucket cache."""

        u = xdrlib.Unpacker(data)

        slot_no = u.unpack_int()
        weight = u.unpack_int()
        ip_address = u.unpack_opaque()
        udp_query_port = u.unpack_int()
        tcp_query_port = u.unpack_int()
        admin_port = u.unpack_int()
        secondary_slot_no = u.unpack_int()

        ipaddr = string.joinfields(map(repr, map(ord, ip_address)), '.')

        if self.debug:
            print "Hash bucket index:", index
            print "slot_no:          ", slot_no
            print "weight:           ", weight
            print "ip_address:       ", hexstr(ip_address)
            print "decoded IP addr:  ", ipaddr
            print "udp_query_port:   ", udp_query_port
            print "tcp_query_port:   ", tcp_query_port
            print "admin_port:       ", admin_port
            print "secondary_slot_no:", secondary_slot_no
            print "="*20

        result = (slot_no, weight, ipaddr, udp_query_port,
                  tcp_query_port, admin_port, secondary_slot_no)
        self.bucket_cache[index] = result


    def set_debuglevel(self, debug):
        """Set the debug level to LEVEL."""
        self.debug = debug


    def get_bucket(self, hdl):
        """For compatibility with HS Admin API's hash_table.Hash_Table"""
        
        slot, weight, ip, udp, tcp, admin, slot2 = self.hash_handle(hdl)

        # We need to combine these hash table classes into one...
        class bucket_lite:
            def __init__(self, weight, ip, udp, tcp, admin):
                self.ip = ip
                self.udp_port = udp
                self.tcp_port = tcp
                self.admin_port = admin

        return bucket_lite(weight, ip, udp, tcp, admin)
    
    def hash_handle(self, hdl):
        """Hash a handle to a tuple describing a handle server bucket.

        Return an 8-tuple containing the bucket fields:
            slot no
            weight
            ipaddr (transformed to a string in dot notation)
            udp query port
            tcp query port
            admin port
            secondary slot no

        A leading "//" is stripped from the handle and it is
        converted to upper case before taking its MD-5 digest.
        The first 'num_of_bits' bits of the digest are then used to
        compute the hash table bucket index; the selected
        bucket is returned from the cache.

        Error is raised when there is no corresponding bucket in the
        cache.

        """

        if self.num_of_bits > 0:
            if hdl[:2] == '//': hdl = hdl[2:]
            hdl = string.upper(hdl)
            digest = md5.new(hdl).digest()
            u = xdrlib.Unpacker(digest)
            index = u.unpack_uint()
            index = (index&0xFFFFFFFFL) >> (32 - self.num_of_bits)
            index = int(index)
        else:
            index = 0

        if self.bucket_cache.has_key(index):
            if self.debug: print "return cached bucket for index", index
            return self.bucket_cache[index]

        raise Error("no bucket found with index %d" % index)


    def get_data(self, hdl, types=[], flags=[], timeout=30, interval=5,
                 command=HP_QUERY, response=HP_QUERY_RESPONSE):
        """Get data for HANDLE of the handle server.

        Optional arguments are a list of desired TYPES, a list of
        FLAGS, a maximum TIMEOUT in seconds (default 30 seconds), a
        retry INTERVAL (default 5 seconds), a COMMAND code (default
        HP_QUERY) and an expected RESPONSE code (default
        HP_QUERY_RESPONSE).

        Exceptions:

        - Error
        - socket.error
        - whatever xdrlib raises

        """

        # XXX Charles says:
        # In get_data function, it always makes a UDP connection. This
        # may not be the case for systems behind firewalls.

        mytag = self.tag.session_tag()

        p = PacketPacker()
        p.pack_header(mytag, command=command)
        p.pack_body(hdl, flags, types)
        request = p.get_buffer()

        (server, qport) = self.hash_handle(hdl)[2:4]

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.debug: print "Send request"
        s.sendto(request, (server, qport))

        expected = 1
        responses = {}
        endtime = time.time() + timeout

        while len(responses) != expected:

            t = time.time()
            if t > endtime:
                raise Error("timed out")
                break

            (readers, writers, extras) = select.select(
                    [s], [], [], min(endtime-t, interval))

            if s not in readers:
                if self.debug: print "Nothing received yet..."
                t = time.time()
                if t+interval < endtime:
                    if self.debug: print "Resend request"
                    s.sendto(request, (server, qport))
                continue

            reply, fromaddr = s.recvfrom(1024)
            u = PacketUnpacker(reply, self.debug)
            (tag, rcommand, err, sequence, total, version) = \
                  u.unpack_header()

            if self.debug:
                print '-'*20
                print "Reply header:"
                print "Version:       ", version
                print "Session tag:   ", tag
                print "Command:       ", rcommand
                print "Sequence#:     ", sequence
                print "#Datagrams:    ", total
                print "Error code:    ", err,
                if error_map.has_key(err):
                    print "(%s)" % error_map[err],
                print
                print '-'*20

            if tag != mytag:
                if self.debug: print "bad session tag"
                continue

            if rcommand != response:
                if self.debug: print "bad reply type"
                continue

            if not 1 <= sequence <= total and not err:
                if self.debug: print "bad sequence number"
                continue

            expected = total
            
            if err != HP_OK:
                if self.debug:
                    print 'err: ', err
                err_info = u.unpack_error_body(err)
                if self.debug:
                    print 'err_info:', `err_info`
                try:
                    err_name = error_map[err]
                except KeyError:
                    err_name = str(err)
                if self.debug:
                    print 'err_name:', `err`
                raise Error(err_name, err, err_info)

            flags, items = u.unpack_reply_body()

            responses[sequence] = (flags, items)

        s.close()

        allflags = None
        allitems = []
        for i in range(1, expected+1):
            if responses.has_key(i):
                (flags, items) = responses[i]
                item = items[0]
                #
                # Check for a continuation packet, if we find one,
                # append it to the previous
                if item[0] < 0:
                    error = "Internal error assembling continuation packets"
                    try:
                        previtem = allitems[-1]
                    except IndexError:
                        raise IOError, error
                    if abs(item[0]) != previtem[0]:
                        raise IOError, error
                    newdata = previtem[1] + item[1]
                    previtem = (previtem[0], newdata)
                    allitems[-1] = previtem
                else:
                    # Normal packet
                    allflags = flags
                    allitems = allitems + items
        return (allflags, allitems)



def hexstr(s):
    """Convert a string to hexadecimal."""
    return "%02x"*len(s) % tuple(map(ord, s))



def fetch_global_hash_table(ht=None, debug=DEBUG):
    """Fetch the global hash table from the default global server."""
    if debug: print "Fetching global hash table"
    if not ht:
        ht = HashTable(server=DEFAULT_GLOBAL_SERVER, debug=debug)
    flags, items = ht.get_data("/service-pointer",
                               command=HP_HASH_REQUEST,
                               response=HP_HASH_RESPONSE)
    hashtable = None
    for type, data in items:
        if type == HDL_TYPE_SERVICE_POINTER:
            # Version 2 of the handle protocol introduces the
            # HANDLE_SERVICE_ID.  This must be checked first.
            # As of 8/10/97 global now implements version 2.
            urnscheme = data[:16]
            if urnscheme == HANDLE_SERVICE_ID:
                hashtable = data[16:]
                # This data is in the same format as file "hdl_hash.tbl"
                if debug: print "hash table data =", hexstr(hashtable)
            else:
                raise Error("Unknown SERVICE_ID: %s" % urnscheme)
    return HashTable(data=hashtable, debug=debug)


def fetch_local_hash_table(hdl, ht=None, debug=DEBUG):
    """Fetch the local hash table for a handle."""

    # XXX Charles says:
    # In fetch_local_hash_table function, does not query Global Handle
    # System for the service handle.

    if debug: print "Fetching local hash table for", `hdl`
    # 1. Get the authority name
    hdl = get_authority(hdl)
    # 2. Prefix the "ha.auth/" authority
    hdl = "ha.auth/" + hdl
    if debug: print "Requesting handle", `hdl`
    # 3. Create a HashTable object if none is provided
    if not ht: ht = HashTable(debug=debug)
    # 4. Send the query and get the reply
    flags, items = ht.get_data(hdl,
                               types=[HDL_TYPE_SERVICE_POINTER,
                                      HDL_TYPE_SERVICE_HANDLE])
    # 5. Inspect the result
    hashtable = None
    handle = None
    for type, data in items:
        if type == HDL_TYPE_SERVICE_HANDLE:
            if debug: print "service handle =", hexstr(data)
            handle = data
        elif type == HDL_TYPE_SERVICE_POINTER:
            urnscheme = data[:16]
            urndata = data[16:]
            if debug: print "URN scheme =", `urnscheme`
            if urnscheme == HANDLE_SERVICE_ID:
                hashtable = urndata
                if debug: print "hash table data =", hexstr(hashtable)
            else:
                raise Error("Unknown SERVICE_ID: %s" % urnscheme)       
        else:
            if debug: print "type", type, "=", data
    if hashtable:
        return HashTable(data=hashtable, debug=debug)
    elif handle:
        flags, items = ht.get_data(handle,
                               types=[HDL_TYPE_SERVICE_POINTER])
        for type, data in items:
            if type == HDL_TYPE_SERVICE_POINTER:
                urnscheme = data[:16]
                urndata = data[16:]
                if debug: print "URN scheme =", `urnscheme`
                if urnscheme == HANDLE_SERVICE_ID:
                    hashtable = urndata
                    if debug: print "hash table data =", hexstr(hashtable)
                    return HashTable(data=hashtable, debug=debug)
                else:
                    raise Error("Unknown SERVICE_ID: %s" % urnscheme)
            else:
                if debug: print "type", type, "=", data

    raise Error("Didn't get a hash table")


def get_authority(hdl):
    """Return the authority name for a handle."""
    if hdl[:2] == "//": hdl = hdl[2:]
    i = string.find(hdl, '/')
    if i >= 0:
        hdl = hdl[:i]
    return string.lower(hdl)


# Test sets

testsets = [
        # 0: Official demo handle (with and without //)
        [
        "//cnri-1/cnri_home",
        "cnri-1/cnri_home",
        ],
        # 1: Some demo handles
        [
        "cnri.dlib/december95",
        "cnri.dlib/november95",
        "CNRI.License/Grail-Version-0.3",
        "CNRI/19970131120001",
        "nonreg.guido/python-home-page",
        "nonreg.guido/python-ftp-dir",
        ],
        # 2: Test various error conditions
        [
        "nonreg.bad.domain/irrelevant",
        "nonreg.guido/non-existing",
        "nonreg.guido/invalid-\1",
        "",
        "nonreg.guido",
        "nonreg.guido/",
        "/",
        "/non-existing",
        ],

        # 3: Test long handles
        [
        "nonreg/" + "x"*100,
        "nonreg/" + "x"*119,
        "nonreg/" + "x"*120,
        "nonreg/" + "x"*121,
        "nonreg/" + "x"*122,
        "nonreg/" + "x"*127,
        "nonreg/" + "x"*128,
        "nonreg/" + "x"*129,
        "nonreg/" + "x"*500,
        ],

        # 4: Test handles on local handle server.
        [
        "10.1000/1",
        "10.1000/2",
        "10.1000/45",
##        "nlm.hdl_test/96053804",
##        "nlm.hdl_test/96047983",
        # The last three handles are known to exploit the poll_data.c
        # bug discovered by Charles on 2/26/96.
##        "nlm.hdl_test/96058248",
##        "nlm.hdl_test/96037846",
##        "nlm.hdl_test/96055523",
        ],
]


usage_msg = """
Usage: hdllib.py [flags] ... [handle] ...

Options:

-a         -- request all data types (by default, only URL data is requested)
-b         -- get the hashtable from the server
-d number  -- request additional (numeric) data type
-f file    -- read the hashtable from this file
-i seconds -- retry interval (default 5.0)
-l         -- on HP_HANDLE_NOT_FOUND, retry using local handle server
-q         -- quiet: the opposite of -v
-t seconds -- timeout (default 30.0)
-s server  -- construct an initial hash table using this server
-v         -- verbose: print heaps of debug info
-0         -- test set 0 (official demo handle; default if no arguments)
-1         -- test set 1 (several demo handles)
-2         -- test set 2 (various error conditions)
-3         -- test set 3 (test parsing errors for long handles)
-4         -- test set 4 (NLM test handles; implies -l and adds to types)
"""


def test(defargs = testsets[0]):
    """Test the HashTable class."""

    import sys
    import getopt

    try:
        opts, args = getopt.getopt(sys.argv[1:], '01234abd:f:i:lqs:t:v')
    except getopt.error, msg:
        print msg
        print usage_msg
        sys.exit(2)

    bootstrap = 0
    local = 0
    debug = DEBUG
    timeout = 30
    interval = 5
    filename = None
    types = [HDL_TYPE_URL]
    flags = []
    server = None
    
    for o, a in opts:
        if o == '-a': types = []
        if o == '-b': bootstrap = 1
        if o == '-d': types.append(string.atoi(a))
        if o == '-f': filename = a
        if o == '-i': interval = string.atof(a)
        if o == '-l': local = 1
        if o == '-q': debug = 0
        if o == '-t': timeout = string.atof(a)
        if o == '-s': server = a
        if o == '-v': debug = debug + 1
        if o == '-0': args = args + testsets[0]
        if o == '-1': args = args + testsets[1]
        if o == '-2': args = args + testsets[2]
        if o == '-3': args = args + testsets[3]
        if o == '-4':
            args = testsets[4]
            local = 1
            if types: types.append(HDL_TYPE_DLS)

    if not args:
        args = defargs

    if bootstrap:
        ht = fetch_global_hash_table(debug=debug)
    else:
        ht = HashTable(filename, debug, server)

    for hdl in args:
        print "Handle:", `hdl`

        try:
            replyflags, items = ht.get_data(
                    hdl, types, flags, timeout, interval)
        except Error, msg:
            if not local or msg.err != HP_HANDLE_NOT_FOUND:
                print "Error:", msg
                print
                continue
            else:
                print "(Retry using local hash table)"
                try:
                    htl = fetch_local_hash_table(hdl, ht=ht, debug=debug)
                    replyflags, items = htl.get_data(
                        hdl, types, flags, timeout, interval)
                except Error, msg:
                    print "Error:", msg
                    print
                    continue

        if debug: print replyflags, items

        bits = 0L
        i = 0
        for c in replyflags:
            bits = bits | (long(ord(c)) << i)
            i = i + 8

        print "flags:", hex(bits),
        for i in range(8 * len(replyflags)):
            if bits & (1L<<i):
                if flags_map.has_key(i):
                    print flags_map[i],
                else:
                    print i,
        print

        if bits & (1L<<HDL_NONMUTABLE): print "\tSTATIC"
        if bits & (1L<<HDL_DISABLED): print "\tDISABLED"

        for stufftype, stuffvalue in items:
            if stufftype in (HDL_TYPE_SERVICE_POINTER,
                             HDL_TYPE_SERVICE_HANDLE):
                stuffvalue = hexstr(stuffvalue)
            else:
                stuffvalue = repr(stuffvalue)
            if data_map.has_key(stufftype):
                s = data_map[stufftype][9:]
            else:
                s = "UNKNOWN(%d)" % stufftype
            print "\t%s/%s" % (s, stuffvalue)
        print


if __name__ == '__main__':
#    import pdb
#    pdb.set_trace()
    test()
