"""One guarded final-hop HTTP exchange; not browser or field performance."""
NUMBERS = ('connect_ms', 'stream_setup_ms', 'first_byte_after_send_ms',
           'headers_after_send_ms', 'body_after_headers_ms', 'exchange_ms')


def validate(value):
    if (type(value) is not dict or set(value) != set(NUMBERS) | {'method','scope','samples'}
            or value['method'] != 'PINNED_HTTP_MONOTONIC_V1'
            or value['scope'] != 'FINAL_HOP_INCLUDES_GUARD_AND_SCHEDULING_NO_DNS'
            or type(value['samples']) is not int or value['samples'] != 1
            or any(type(value[k]) is not int or not 0<=value[k]<=600000 for k in NUMBERS)
            or value['first_byte_after_send_ms'] > value['headers_after_send_ms']
            or value['headers_after_send_ms']+value['body_after_headers_ms'] > value['exchange_ms']
            or value['connect_ms']+value['stream_setup_ms'] > value['exchange_ms']):
        raise ValueError('HTTP_MEASUREMENT_INTEGRITY')


def measure(start, connected, secured, sent, first, headers, finished):
    offsets = [round((v-start)*1000) for v in (connected,secured,sent,first,headers,finished)]
    c,s,w,f,h,e = offsets
    value={'method':'PINNED_HTTP_MONOTONIC_V1',
        'scope':'FINAL_HOP_INCLUDES_GUARD_AND_SCHEDULING_NO_DNS','samples':1,
        'connect_ms':c,'stream_setup_ms':s-c,'first_byte_after_send_ms':f-w,
        'headers_after_send_ms':h-w,'body_after_headers_ms':e-h,'exchange_ms':e}
    validate(value)
    return value
